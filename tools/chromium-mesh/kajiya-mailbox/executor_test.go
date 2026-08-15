package kajiyamailbox

import (
	"fmt"
	"testing"

	iradix "github.com/hashicorp/go-immutable-radix/v2"
	"go.chromium.org/build/kajiya/digest"
	"go.chromium.org/build/kajiya/execution/model"
)

type fakeTransport struct {
	got Request
}

func (f *fakeTransport) Execute(req Request) (Response, error) {
	f.got = req
	return Response{
		ExitCode: 7,
		Stdout:   []byte("mailbox-out"),
		Stderr:   []byte("mailbox-err"),
		OutputFiles: map[string]OutputFileData{
			"out.txt": {Data: []byte("worker-output")},
		},
	}, nil
}

type fakeCAS struct {
	blobs map[string][]byte
}

func newFakeCAS() *fakeCAS { return &fakeCAS{blobs: map[string][]byte{}} }

func (c *fakeCAS) Get(d digest.Digest) ([]byte, error) {
	b, ok := c.blobs[d.String()]
	if !ok {
		return nil, fmt.Errorf("missing %s", d.String())
	}
	return append([]byte(nil), b...), nil
}

func (c *fakeCAS) Put(data []byte) (digest.Digest, error) {
	d := digest.NewFromBlob(data)
	c.blobs[d.String()] = append([]byte(nil), data...)
	return d, nil
}

func trieWithInputAndOutput(input digest.Digest) *model.DirectoryTrie {
	t := iradix.New[*model.KajiyaDirectory]()
	tx := t.Txn()
	tx.Insert([]byte(""), &model.KajiyaDirectory{
		Files:   []model.KajiyaFile{{Name: "input.txt", Digest: input, UnixMode: 0644}},
		Outputs: []model.KajiyaOutput{{Name: "out.txt", Type: model.File}},
	})
	return tx.Commit()
}

func TestExecutorRoundTrip(t *testing.T) {
	cas := newFakeCAS()
	inputDigest, err := cas.Put([]byte("input-data"))
	if err != nil {
		t.Fatal(err)
	}
	tr := &fakeTransport{}
	ex := &Executor{Transport: tr, CAS: cas}
	a := &model.Action{
		Args:       []string{"tool", "--flag"},
		EnvVars:    []model.EnvVar{{Name: "TF_TEST", Value: "yes"}},
		WorkingDir: ".",
		Platform:   map[string][]string{"OSFamily": {"Linux"}},
		InputTrie:  trieWithInputAndOutput(inputDigest),
	}

	r, err := ex.Execute(a)
	if err != nil {
		t.Fatal(err)
	}
	if tr.got.Protocol != Protocol || tr.got.Args[0] != "tool" || tr.got.Environment["TF_TEST"] != "yes" {
		t.Fatalf("bad request: %#v", tr.got)
	}
	if string(tr.got.Blobs[inputDigest.String()]) != "input-data" {
		t.Fatalf("input blob did not cross data plane: %#v", tr.got.Blobs)
	}
	if len(tr.got.Tree.Files) != 1 || len(tr.got.Tree.Outputs) != 1 {
		t.Fatalf("unexpected tree: %#v", tr.got.Tree)
	}
	if r.ExitCode != 7 || string(r.StdoutRaw) != "mailbox-out" || string(r.StderrRaw) != "mailbox-err" {
		t.Fatalf("bad result: %#v", r)
	}
	if len(r.OutputFiles) != 1 || r.OutputFiles[0].Path != "out.txt" {
		t.Fatalf("bad output files: %#v", r.OutputFiles)
	}
	key := fmt.Sprintf("%s/%d", r.OutputFiles[0].Digest.Hash, r.OutputFiles[0].Digest.SizeBytes)
	if got := string(cas.blobs[key]); got != "worker-output" {
		t.Fatalf("output bytes not returned to CAS: %q", got)
	}
}
