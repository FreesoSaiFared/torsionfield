// Package kajiyamailbox provides the execution seam between Kajiya's REAPI
// frontend and a transport that may run an action on another VM.
package kajiyamailbox

import (
	"errors"
	"fmt"
	"time"

	repb "github.com/bazelbuild/remote-apis/build/bazel/remote/execution/v2"
	"go.chromium.org/build/kajiya/execution"
	"go.chromium.org/build/kajiya/execution/model"
)

const Protocol = "TORSIONFIELD_KAJIYA_MAILBOX/1"

// Request is deliberately transport-neutral. Input-root bytes remain owned by
// the Kajiya/CAS adapter; this envelope carries action identity and execution
// semantics to a live worker or an offline mailbox exporter.
type Request struct {
	Protocol        string              `json:"protocol"`
	ActionDigest    string              `json:"action_digest"`
	CommandDigest   string              `json:"command_digest"`
	InputRootDigest string              `json:"input_root_digest"`
	Args            []string            `json:"args"`
	Environment     map[string]string   `json:"environment"`
	WorkingDir      string              `json:"working_dir"`
	OutputPaths     []string            `json:"output_paths"`
	Timeout         time.Duration       `json:"timeout"`
	Platform        map[string][]string `json:"platform"`
	ContainerImage  string              `json:"container_image,omitempty"`
}

// Response is the worker-facing result before Kajiya's CAS adapter imports
// returned output bytes and constructs canonical REAPI output digests.
type Response struct {
	ExitCode int32
	Stdout   []byte
	Stderr   []byte
}

// Transport is intentionally smaller than REAPI. Kajiya remains the REAPI/CAS
// authority; this transport only decides where an already-normalized action is
// executed.
type Transport interface {
	Execute(Request) (Response, error)
}

// Executor implements Kajiya's execution.ExecutorInterface. The first version
// proves the replaceable seam and stdout/stderr/exit-code round trip. Input and
// output CAS materialization is added by the next adapter layer.
type Executor struct {
	Transport Transport
}

var _ execution.ExecutorInterface = (*Executor)(nil)

func (e *Executor) Execute(action *model.Action) (*repb.ActionResult, error) {
	if action == nil {
		return nil, errors.New("nil Kajiya action")
	}
	if e.Transport == nil {
		return nil, errors.New("nil mailbox transport")
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
		OutputPaths:     append([]string(nil), action.OutputPaths...),
		Timeout:         action.Timeout,
		Platform:        clonePlatform(action.Platform),
		ContainerImage:  action.ContainerImage,
	}

	resp, err := e.Transport.Execute(req)
	if err != nil {
		return nil, err
	}
	return &repb.ActionResult{
		ExitCode: resp.ExitCode,
		StdoutRaw: append([]byte(nil), resp.Stdout...),
		StderrRaw: append([]byte(nil), resp.Stderr...),
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
