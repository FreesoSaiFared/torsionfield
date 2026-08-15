package kajiyamailbox

import (
	"fmt"
	"sort"

	repb "go.chromium.org/build/remote-apis/build/bazel/remote/execution/v2"
	"go.chromium.org/build/kajiya/blobstore"
	"go.chromium.org/build/kajiya/execution/model"
)

// OutputFileData is returned by a worker for a declared regular-file output.
type OutputFileData struct {
	Data       []byte `json:"data"`
	Executable bool   `json:"executable"`
}

// loadInputBlobs intentionally accepts Kajiya's concrete CAS. This allows the
// exact digest type carried by KajiyaFile to flow directly into CAS.Get without
// creating a second digest abstraction that can drift across Kajiya revisions.
func loadInputBlobs(action *model.Action, cas *blobstore.ContentAddressableStorage) (map[string][]byte, error) {
	if action == nil || action.InputTrie == nil {
		return nil, fmt.Errorf("action has no Kajiya InputTrie")
	}
	if cas == nil {
		return nil, fmt.Errorf("nil Kajiya CAS")
	}
	blobs := map[string][]byte{}
	var walkErr error
	action.InputTrie.Root().Walk(func(_ []byte, d *model.KajiyaDirectory) bool {
		if d == nil {
			walkErr = fmt.Errorf("nil Kajiya directory")
			return true
		}
		for _, f := range d.Files {
			key := f.Digest.String()
			if _, ok := blobs[key]; ok {
				continue
			}
			b, err := cas.Get(f.Digest)
			if err != nil {
				walkErr = fmt.Errorf("fetch input blob %s: %w", key, err)
				return true
			}
			blobs[key] = b
		}
		return false
	})
	if walkErr != nil {
		return nil, walkErr
	}
	return blobs, nil
}

func storeOutputFiles(cas *blobstore.ContentAddressableStorage, tree ActionTree, returned map[string]OutputFileData) ([]*repb.OutputFile, error) {
	if cas == nil {
		return nil, fmt.Errorf("nil Kajiya CAS")
	}
	declared := map[string]bool{}
	for _, out := range tree.Outputs {
		if out.Type != int(model.File) {
			return nil, fmt.Errorf("unsupported declared output type path=%q type=%d", out.Path, out.Type)
		}
		declared[out.Path] = true
	}

	paths := make([]string, 0, len(returned))
	for p := range returned {
		paths = append(paths, p)
	}
	sort.Strings(paths)

	files := make([]*repb.OutputFile, 0, len(paths))
	for _, p := range paths {
		if !declared[p] {
			return nil, fmt.Errorf("worker returned undeclared output %q", p)
		}
		data := returned[p]
		d, err := cas.Put(data.Data)
		if err != nil {
			return nil, fmt.Errorf("store output %q: %w", p, err)
		}
		files = append(files, &repb.OutputFile{
			Path:         p,
			Digest:       d.ToProto(),
			IsExecutable: data.Executable,
		})
	}
	return files, nil
}
