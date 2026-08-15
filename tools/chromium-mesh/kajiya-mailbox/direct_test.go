package kajiyamailbox

import (
	"runtime"
	"testing"
	"time"
)

func TestDirectTransportExecutesDeclaredFileAction(t *testing.T) {
	if runtime.GOOS == "windows" {
		t.Skip("shell fixture is Unix-only; Chromium Linux mesh is the first target")
	}
	req := Request{
		Protocol: Protocol,
		Args: []string{"/bin/sh", "-c", "cat input.txt > out.txt; printf TF_DIRECT_OK"},
		WorkingDir: ".",
		Timeout: 10 * time.Second,
		Tree: ActionTree{
			Files: []InputFile{{Path: "input.txt", Digest: "blob-1", UnixMode: 0644}},
			Outputs: []DeclaredOutput{{Path: "out.txt", Type: 0}},
		},
		Blobs: map[string][]byte{"blob-1": []byte("chromium-mesh\n")},
	}
	res, err := (DirectTransport{BaseDir: t.TempDir()}).Execute(req)
	if err != nil {
		t.Fatal(err)
	}
	if res.ExitCode != 0 || string(res.Stdout) != "TF_DIRECT_OK" {
		t.Fatalf("unexpected execution result: %#v", res)
	}
	if got := string(res.OutputFiles["out.txt"].Data); got != "chromium-mesh\n" {
		t.Fatalf("unexpected output bytes %q", got)
	}
}

func TestDirectTransportRejectsEscapingSymlink(t *testing.T) {
	req := Request{
		Protocol: Protocol,
		Args: []string{"/bin/true"},
		Tree: ActionTree{Symlinks: []InputSymlink{{Path: "bad", Target: "../outside"}}},
	}
	if _, err := (DirectTransport{BaseDir: t.TempDir()}).Execute(req); err == nil {
		t.Fatal("expected escaping symlink rejection")
	}
}
