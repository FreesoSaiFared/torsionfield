package main

import (
	"io"
	"net/http"
	"os"
	"path/filepath"
	"strings"
	"testing"

	wpr "go.chromium.org/webpagereplay/src/webpagereplay"
)

func strp(s string) *string { return &s }
func intp(v int) *int       { return &v }

func TestConvertProducesReadableWPRArchive(t *testing.T) {
	dir := t.TempDir()
	output := filepath.Join(dir, "capture.wprgo")

	status := 200
	responseHeaders := `{"content-type":"application/json","content-encoding":"gzip","transfer-encoding":"chunked","set-cookie":"sid=secret; Path=/"}`
	requestHeaders := `{"Accept":"application/json","Authorization":"Bearer secret","Cookie":"a=b"}`
	body := `{"answer":42}`
	duration := int64(17)

	requests := []capturedRequest{{
		ID: "s-1", SessionID: "s", Sequence: 1, Timestamp: 100,
		Method: "GET", URL: "http://replay.test/api",
		RequestHeaders: requestHeaders, StatusCode: &status,
		ResponseHeaders: &responseHeaders, ResponseBody: &body,
		ContentType: strp("application/json"), DurationMS: &duration, Source: "cdp",
	}}

	analysis, err := convert(requests, output, options{StrictURL: true})
	if err != nil {
		t.Fatal(err)
	}
	if analysis.ReplayableCount != 1 || analysis.SkippedCount != 0 {
		t.Fatalf("unexpected analysis counts: %+v", analysis)
	}
	if !analysis.Requests[0].HasAuthHeader || !analysis.Requests[0].HasCookie || !analysis.Requests[0].HasSetCookie {
		t.Fatalf("sensitive-header indicators missing: %+v", analysis.Requests[0])
	}

	archive, err := wpr.OpenArchive(output)
	if err != nil {
		t.Fatal(err)
	}
	if !archive.DisableFuzzyURLMatching {
		t.Fatal("strict URL flag was not preserved")
	}
	if !archive.ServeResponseInChronologicalSequence {
		t.Fatal("chronological serving flag was not preserved")
	}
	if !strings.Contains(archive.Metadata, anythingAnalyzerPin) || !strings.Contains(archive.Metadata, wprPin) {
		t.Fatalf("metadata missing donor pins: %q", archive.Metadata)
	}

	req, _ := http.NewRequest("GET", "http://replay.test/api", nil)
	req.Header.Set("Accept", "application/json")
	req.Header.Set("Authorization", "Bearer secret")
	req.Header.Set("Cookie", "a=b")
	_, resp, err := archive.FindRequest(req)
	if err != nil {
		t.Fatal(err)
	}
	got, err := io.ReadAll(resp.Body)
	if err != nil {
		t.Fatal(err)
	}
	if string(got) != body {
		t.Fatalf("body = %q, want %q", got, body)
	}
	if resp.Header.Get("Content-Encoding") != "" {
		t.Fatalf("decoded capture retained content-encoding: %q", resp.Header.Get("Content-Encoding"))
	}
	if resp.Header.Get("Transfer-Encoding") != "" {
		t.Fatalf("retained transfer-encoding: %q", resp.Header.Get("Transfer-Encoding"))
	}
	if resp.Header.Get("Content-Length") != "13" {
		t.Fatalf("content-length = %q", resp.Header.Get("Content-Length"))
	}
}

func TestConvertPreservesDuplicateChronology(t *testing.T) {
	output := filepath.Join(t.TempDir(), "dupes.wprgo")
	status := 200
	headers := `{"content-type":"text/plain"}`
	a, b := "first", "second"
	requests := []capturedRequest{
		{ID: "2", SessionID: "s", Sequence: 2, Method: "GET", URL: "http://replay.test/same", RequestHeaders: "{}", StatusCode: &status, ResponseHeaders: &headers, ResponseBody: &b},
		{ID: "1", SessionID: "s", Sequence: 1, Method: "GET", URL: "http://replay.test/same", RequestHeaders: "{}", StatusCode: &status, ResponseHeaders: &headers, ResponseBody: &a},
	}
	if _, err := convert(requests, output, options{}); err != nil {
		t.Fatal(err)
	}

	archive, err := wpr.OpenArchive(output)
	if err != nil {
		t.Fatal(err)
	}
	req, _ := http.NewRequest("GET", "http://replay.test/same", nil)
	_, resp1, err := archive.FindRequest(req)
	if err != nil {
		t.Fatal(err)
	}
	got1, _ := io.ReadAll(resp1.Body)
	_, resp2, err := archive.FindRequest(req)
	if err != nil {
		t.Fatal(err)
	}
	got2, _ := io.ReadAll(resp2.Body)
	if string(got1) != "first" || string(got2) != "second" {
		t.Fatalf("chronology = %q then %q", got1, got2)
	}
}

func TestConvertSkipsNonReplayableRecords(t *testing.T) {
	output := filepath.Join(t.TempDir(), "skip.wprgo")
	requests := []capturedRequest{
		{ID: "missing", Sequence: 1, Method: "GET", URL: "https://example.test/no-response", RequestHeaders: "{}"},
		{ID: "ws", Sequence: 2, Method: "GET", URL: "https://example.test/socket", RequestHeaders: "{}", StatusCode: intp(101), ResponseHeaders: strp(`{"upgrade":"websocket"}`), IsWebSocket: true},
	}
	analysis, err := convert(requests, output, options{})
	if err != nil {
		t.Fatal(err)
	}
	if analysis.ReplayableCount != 0 || analysis.SkippedCount != 2 {
		t.Fatalf("counts: %+v", analysis)
	}
	if _, err := os.Stat(output); err != nil {
		t.Fatal(err)
	}
}
