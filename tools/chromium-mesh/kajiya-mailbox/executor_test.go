package kajiyamailbox

import (
	"strings"
	"testing"

	"go.chromium.org/build/kajiya/execution/model"
)

type fakeTransport struct {
	got Request
}

func (f *fakeTransport) Execute(req Request) (Response, error) {
	f.got = req
	return Response{ExitCode: 0, Stdout: []byte("mailbox-out")}, nil
}

// The concrete Kajiya CAS is deliberately part of Executor's type now, so this
// unit test checks the fail-closed boundary without inventing a second digest
// interface. A real-CAS integration test is added at the Kajiya server layer.
func TestExecutorRejectsNilCAS(t *testing.T) {
	ex := &Executor{Transport: &fakeTransport{}}
	_, err := ex.Execute(&model.Action{})
	if err == nil || !strings.Contains(err.Error(), "nil Kajiya CAS") {
		t.Fatalf("expected nil CAS rejection, got %v", err)
	}
}

func TestClonePlatform(t *testing.T) {
	src := map[string][]string{"OSFamily": {"Linux"}}
	dst := clonePlatform(src)
	dst["OSFamily"][0] = "changed"
	if src["OSFamily"][0] != "Linux" {
		t.Fatal("clonePlatform aliased source")
	}
}
