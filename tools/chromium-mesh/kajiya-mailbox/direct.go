package kajiyamailbox

import (
	"context"
	"errors"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"sort"
	"strings"
	"time"
)

// DirectTransport executes a normalized mailbox request in a fresh private
// filesystem root. It exists to prove the Kajiya ExecutorInterface data plane
// without nsjail. The same Request/Response contract is used by remote mailbox
// workers; DirectTransport is not the final distributed scheduler.
type DirectTransport struct {
	BaseDir string
}

func safeLocalPath(root, rel string) (string, error) {
	if rel == "" || rel == "." {
		return root, nil
	}
	if filepath.IsAbs(rel) {
		return "", fmt.Errorf("absolute action path %q", rel)
	}
	clean := filepath.Clean(rel)
	if clean == ".." || strings.HasPrefix(clean, ".."+string(filepath.Separator)) {
		return "", fmt.Errorf("action path escapes root: %q", rel)
	}
	p := filepath.Join(root, clean)
	r, err := filepath.Rel(root, p)
	if err != nil || r == ".." || strings.HasPrefix(r, ".."+string(filepath.Separator)) {
		return "", fmt.Errorf("action path escapes root: %q", rel)
	}
	return p, nil
}

func (d DirectTransport) Execute(req Request) (Response, error) {
	if req.Protocol != Protocol {
		return Response{}, fmt.Errorf("unsupported mailbox protocol %q", req.Protocol)
	}
	base := d.BaseDir
	if base == "" {
		base = os.TempDir()
	}
	if err := os.MkdirAll(base, 0755); err != nil {
		return Response{}, err
	}
	root, err := os.MkdirTemp(base, "tf-kajiya-action-")
	if err != nil {
		return Response{}, err
	}
	defer os.RemoveAll(root)

	for _, f := range req.Tree.Files {
		data, ok := req.Blobs[f.Digest]
		if !ok {
			return Response{}, fmt.Errorf("missing action blob %s for %s", f.Digest, f.Path)
		}
		p, err := safeLocalPath(root, f.Path)
		if err != nil {
			return Response{}, err
		}
		if err := os.MkdirAll(filepath.Dir(p), 0755); err != nil {
			return Response{}, err
		}
		mode := os.FileMode(f.UnixMode)
		if mode == 0 {
			mode = 0644
		}
		if err := os.WriteFile(p, data, mode); err != nil {
			return Response{}, err
		}
		if err := os.Chmod(p, mode); err != nil {
			return Response{}, err
		}
	}

	for _, s := range req.Tree.Symlinks {
		if filepath.IsAbs(s.Target) || s.Target == ".." || strings.HasPrefix(filepath.Clean(s.Target), ".."+string(filepath.Separator)) {
			return Response{}, fmt.Errorf("mailbox v1 rejects escaping symlink %s -> %s", s.Path, s.Target)
		}
		p, err := safeLocalPath(root, s.Path)
		if err != nil {
			return Response{}, err
		}
		if err := os.MkdirAll(filepath.Dir(p), 0755); err != nil {
			return Response{}, err
		}
		if err := os.Symlink(s.Target, p); err != nil {
			return Response{}, err
		}
	}

	cwd, err := safeLocalPath(root, req.WorkingDir)
	if err != nil {
		return Response{}, err
	}
	if err := os.MkdirAll(cwd, 0755); err != nil {
		return Response{}, err
	}
	if len(req.Args) == 0 {
		return Response{}, errors.New("empty action argv")
	}

	timeout := req.Timeout
	if timeout <= 0 {
		timeout = 10 * time.Minute
	}
	ctx, cancel := context.WithTimeout(context.Background(), timeout)
	defer cancel()
	cmd := exec.CommandContext(ctx, req.Args[0], req.Args[1:]...)
	cmd.Dir = cwd
	keys := make([]string, 0, len(req.Environment))
	for k := range req.Environment {
		keys = append(keys, k)
	}
	sort.Strings(keys)
	cmd.Env = make([]string, 0, len(keys))
	for _, k := range keys {
		cmd.Env = append(cmd.Env, k+"="+req.Environment[k])
	}
	var stdout, stderr strings.Builder
	cmd.Stdout = &stdout
	cmd.Stderr = &stderr
	runErr := cmd.Run()
	if ctx.Err() == context.DeadlineExceeded {
		return Response{}, fmt.Errorf("action timeout after %s", timeout)
	}
	exitCode := int32(0)
	if runErr != nil {
		var ee *exec.ExitError
		if !errors.As(runErr, &ee) {
			return Response{}, runErr
		}
		exitCode = int32(ee.ExitCode())
	}

	outputs := map[string]OutputFileData{}
	for _, out := range req.Tree.Outputs {
		p, err := safeLocalPath(root, out.Path)
		if err != nil {
			return Response{}, err
		}
		st, err := os.Stat(p)
		if err != nil {
			if os.IsNotExist(err) && exitCode != 0 {
				continue
			}
			return Response{}, fmt.Errorf("declared output %q: %w", out.Path, err)
		}
		if !st.Mode().IsRegular() {
			return Response{}, fmt.Errorf("declared output %q is not a regular file", out.Path)
		}
		b, err := os.ReadFile(p)
		if err != nil {
			return Response{}, err
		}
		outputs[out.Path] = OutputFileData{Data: b, Executable: st.Mode()&0111 != 0}
	}
	return Response{
		ExitCode:    exitCode,
		Stdout:      []byte(stdout.String()),
		Stderr:      []byte(stderr.String()),
		OutputFiles: outputs,
	}, nil
}
