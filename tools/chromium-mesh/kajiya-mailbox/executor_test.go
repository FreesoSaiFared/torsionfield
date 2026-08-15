package kajiyamailbox

import (
	"testing"

	iradix "github.com/hashicorp/go-immutable-radix/v2"
	"go.chromium.org/build/kajiya/execution/model"
)

type fakeTransport struct {
	got Request
}

func (f *fakeTransport) Execute(req Request) (Response, error) {
	f.got = req
	return Response{ExitCode: 7, Stdout: []byte("mailbox-out"), Stderr: []byte("mailbox-err")}, nil
}

func emptyTrie() *model.DirectoryTrie {
	t := iradix.New[*model.KajiyaDirectory]()
	tx := t.Txn()
	tx.Insert([]byte(""), &model.KajiyaDirectory{})
	return tx.Commit()
}

func TestExecutorRoundTrip(t *testing.T) {
	tr := &fakeTransport{}
	ex := &Executor{Transport: tr}
	a := &model.Action{
		Args:       []string{"tool", "--flag"},
		EnvVars:    []model.EnvVar{{Name: "TF_TEST", Value: "yes"}},
		WorkingDir: "out/Default",
		Platform:   map[string][]string{"OSFamily": {"Linux"}},
		InputTrie:  emptyTrie(),
	}

	r, err := ex.Execute(a)
	if err != nil {
		t.Fatal(err)
	}
	if tr.got.Protocol != Protocol || tr.got.Args[0] != "tool" || tr.got.Environment["TF_TEST"] != "yes" {
		t.Fatalf("bad request: %#v", tr.got)
	}
	if len(tr.got.Tree.Files) != 0 || len(tr.got.Tree.Outputs) != 0 {
		t.Fatalf("unexpected tree: %#v", tr.got.Tree)
	}
	if r.ExitCode != 7 || string(r.StdoutRaw) != "mailbox-out" || string(r.StderrRaw) != "mailbox-err" {
		t.Fatalf("bad result: %#v", r)
	}
}
