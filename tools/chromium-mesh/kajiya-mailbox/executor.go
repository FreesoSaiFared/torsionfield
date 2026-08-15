// Package kajiyamailbox provides the execution seam between Kajiya's REAPI
// frontend and a transport that may run an action on another VM.
package kajiyamailbox

import (
	"errors"
	"fmt"
	"time"

	repb "go.chromium.org/build/remote-apis/build/bazel/remote/execution/v2"
	"go.chromium.org/build/kajiya/execution"
	"go.chromium.org/build/kajiya/execution/model"
)

const Protocol = "TORSIONFIELD_KAJIYA_MAILBOX/1"

// Request is deliberately transport-neutral. Kajiya remains authoritative for
// the REAPI Merkle input/output model. Tree is derived directly from the exact
// immutable Kajiya InputTrie, never from a second source/dependency scan.
type Request struct {
	Protocol        string              `json:"protocol"`
	ActionDigest    string              `json:"action_digest"`
	CommandDigest   string              `json:"command_digest"`
	InputRootDigest string              `json:"input_root_digest"`
	Args            []string            `json:"args"`
	Environment     map[string]string   `json:"environment"`
	WorkingDir      string              `json:"working_dir"`
	Timeout         time.Duration       `json:"timeout"`
	Platform        map[string][]string `json:"platform"`
	ContainerImage  string              `json:"container_image,omitempty"`
	Tree            ActionTree          `json:"tree"`
	Blobs           map[string][]byte   `json:"blobs"`
}

// Response is the worker-facing result. Regular-file outputs are returned as
// bytes and are inserted into Kajiya's canonical CAS by Executor before the
// REAPI ActionResult is returned to Siso.
type Response struct {
	ExitCode    int32                     `json:"exit_code"`
	Stdout      []byte                    `json:"stdout"`
	Stderr      []byte                    `json:"stderr"`
	OutputFiles map[string]OutputFileData `json:"output_files,omitempty"`
}

// Transport is intentionally smaller than REAPI. Kajiya remains the REAPI/CAS
// authority; this transport only decides where an already-normalized action is
// executed.
type Transport interface {
	Execute(Request) (Response, error)
}

// Executor implements Kajiya's execution.ExecutorInterface. CAS is the exact
// Kajiya CAS used by the REAPI server; Transport may be a live remote worker or
// an offline mailbox exporter/importer.
type Executor struct {
	Transport Transport
	CAS       BlobCAS
}

var _ execution.ExecutorInterface = (*Executor)(nil)

func (e *Executor) Execute(action *model.Action) (*repb.ActionResult, error) {
	if action == nil {
		return nil, errors.New("nil Kajiya action")
	}
	if e.Transport == nil {
		return nil, errors.New("nil mailbox transport")
	}
	if e.CAS == nil {
		return nil, errors.New("nil Kajiya CAS")
	}
	if action.ContainerImage != "" {
		return nil, fmt.Errorf("container-image actions are not admitted by mailbox v1")
	}
	if action.CaptureWholeTree {
		return nil, fmt.Errorf("capture-whole-tree actions are not admitted by mailbox v1")
	}

	tree, err := FlattenAction(action)
	if err != nil {
		return nil, err
	}
	for _, out := range tree.Outputs {
		if out.Type != int(model.File) {
			return nil, fmt.Errorf("mailbox v1 supports regular-file outputs only: path=%q type=%d", out.Path, out.Type)
		}
	}
	blobs, err := loadInputBlobs(action, e.CAS)
	if err != nil {
		return nil, err
	}
	env := make(map[string]string, len(action.EnvVars))
	for _, item := range action.EnvVars {
		env[item.Name] = item.Value
	}

	req := Request{
		Protocol:        Protocol,
		ActionDigest:    fmt.Sprint(action.ActionDigest),
		CommandDigest:   fmt.Sprint(action.CommandDigest),
		InputRootDigest: fmt.Sprint(action.InputRootDigest),
		Args:            append([]string(nil), action.Args...),
		Environment:     env,
		WorkingDir:      action.WorkingDir,
		Timeout:         action.Timeout,
		Platform:        clonePlatform(action.Platform),
		ContainerImage:  action.ContainerImage,
		Tree:            tree,
		Blobs:           blobs,
	}

	resp, err := e.Transport.Execute(req)
	if err != nil {
		return nil, err
	}
	outputs, err := storeOutputFiles(e.CAS, tree, resp.OutputFiles)
	if err != nil {
		return nil, err
	}
	return &repb.ActionResult{
		ExitCode:    resp.ExitCode,
		StdoutRaw:   append([]byte(nil), resp.Stdout...),
		StderrRaw:   append([]byte(nil), resp.Stderr...),
		OutputFiles: outputs,
	}, nil
}

func clonePlatform(src map[string][]string) map[string][]string {
	if src == nil {
		return nil
	}
	dst := make(map[string][]string, len(src))
	for key, values := range src {
		dst[key] = append([]string(nil), values...)
	}
	return dst
}
