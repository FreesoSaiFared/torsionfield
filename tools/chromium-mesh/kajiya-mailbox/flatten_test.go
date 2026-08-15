package kajiyamailbox

import (
	"testing"

	"go.chromium.org/build/kajiya/execution/model"
)

func TestFlattenDirectory(t *testing.T) {
	d := &model.KajiyaDirectory{
		Files: []model.KajiyaFile{{Name: "input.h", UnixMode: 0644}},
		Symlinks: []model.KajiyaSymlink{{Name: "alias.h", Target: "input.h"}},
		Outputs: []model.KajiyaOutput{{Name: "obj/a.o", Type: model.File}},
	}
	var got ActionTree
	if err := flattenDirectory("base/types", d, &got); err != nil {
		t.Fatal(err)
	}
	if len(got.Files) != 1 || got.Files[0].Path != "base/types/input.h" {
		t.Fatalf("bad files: %#v", got.Files)
	}
	if len(got.Symlinks) != 1 || got.Symlinks[0].Path != "base/types/alias.h" {
		t.Fatalf("bad symlinks: %#v", got.Symlinks)
	}
	if len(got.Outputs) != 1 || got.Outputs[0].Path != "base/types/obj/a.o" {
		t.Fatalf("bad outputs: %#v", got.Outputs)
	}
}

func TestRejectTraversal(t *testing.T) {
	if _, err := cleanRelative("", "../escape"); err == nil {
		t.Fatal("expected traversal rejection")
	}
}
