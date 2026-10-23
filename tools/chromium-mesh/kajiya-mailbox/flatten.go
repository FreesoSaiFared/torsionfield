package kajiyamailbox

import (
	"fmt"
	"path"
	"strings"

	"go.chromium.org/build/kajiya/execution/model"
)

// InputFile is one canonical Kajiya CAS-backed file required by an action.
type InputFile struct {
	Path     string `json:"path"`
	Digest   string `json:"digest"`
	UnixMode uint32 `json:"unix_mode"`
}

// InputSymlink preserves a symlink exactly as represented by Kajiya's action model.
type InputSymlink struct {
	Path   string `json:"path"`
	Target string `json:"target"`
}

// DeclaredOutput comes from Kajiya's already-validated command/output model.
type DeclaredOutput struct {
	Path string `json:"path"`
	Type int    `json:"type"`
}

// ActionTree is the transport-neutral manifest derived from Kajiya's canonical
// DirectoryTrie. File bytes are intentionally not copied here; the CAS adapter
// resolves each digest only when constructing a live or mailbox payload.
type ActionTree struct {
	Files    []InputFile      `json:"files"`
	Symlinks []InputSymlink   `json:"symlinks"`
	Outputs  []DeclaredOutput `json:"outputs"`
}

func cleanRelative(prefix, name string) (string, error) {
	p := path.Clean(path.Join(prefix, name))
	if p == "." || strings.HasPrefix(p, "/") || p == ".." || strings.HasPrefix(p, "../") {
		return "", fmt.Errorf("unsafe REAPI path %q", p)
	}
	return p, nil
}

func flattenDirectory(prefix string, d *model.KajiyaDirectory, dst *ActionTree) error {
	if d == nil {
		return fmt.Errorf("nil Kajiya directory at %q", prefix)
	}
	for _, f := range d.Files {
		p, err := cleanRelative(prefix, f.Name)
		if err != nil {
			return err
		}
		dst.Files = append(dst.Files, InputFile{
			Path:     p,
			Digest:   f.Digest.String(),
			UnixMode: uint32(f.UnixMode),
		})
	}
	for _, s := range d.Symlinks {
		p, err := cleanRelative(prefix, s.Name)
		if err != nil {
			return err
		}
		dst.Symlinks = append(dst.Symlinks, InputSymlink{Path: p, Target: s.Target})
	}
	for _, o := range d.Outputs {
		p, err := cleanRelative(prefix, o.Name)
		if err != nil {
			return err
		}
		dst.Outputs = append(dst.Outputs, DeclaredOutput{Path: p, Type: int(o.Type)})
	}
	return nil
}

// FlattenAction walks the exact immutable DirectoryTrie created by Kajiya from
// the REAPI Action/Command/InputRoot. No source-tree scanning occurs here.
func FlattenAction(action *model.Action) (ActionTree, error) {
	var out ActionTree
	if action == nil || action.InputTrie == nil {
		return out, fmt.Errorf("action has no Kajiya InputTrie")
	}
	var walkErr error
	action.InputTrie.Root().Walk(func(k []byte, d *model.KajiyaDirectory) bool {
		if err := flattenDirectory(string(k), d, &out); err != nil {
			walkErr = err
			return true
		}
		return false
	})
	if walkErr != nil {
		return ActionTree{}, walkErr
	}
	return out, nil
}
