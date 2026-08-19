package main

import (
	"bytes"
	"encoding/json"
	"errors"
	"flag"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"os"
	"sort"
	"strconv"
	"strings"

	wpr "go.chromium.org/webpagereplay/src/webpagereplay"
)

const (
	converterVersion    = "0.1.0"
	anythingAnalyzerPin = "0ed4791688e5186da051c85eb7ddfe4639e14fd2"
	wprPin              = "b2b856131e36c99e9de9c419fe8ca02f857082ba"
)

type capturedRequest struct {
	ID              string  `json:"id"`
	SessionID       string  `json:"session_id"`
	Sequence        int     `json:"sequence"`
	Timestamp       int64   `json:"timestamp"`
	Method          string  `json:"method"`
	URL             string  `json:"url"`
	RequestHeaders  string  `json:"request_headers"`
	RequestBody     *string `json:"request_body"`
	StatusCode      *int    `json:"status_code"`
	ResponseHeaders *string `json:"response_headers"`
	ResponseBody    *string `json:"response_body"`
	ContentType     *string `json:"content_type"`
	Initiator       *string `json:"initiator"`
	DurationMS      *int64  `json:"duration_ms"`
	IsStreaming     bool    `json:"is_streaming"`
	IsWebSocket     bool    `json:"is_websocket"`
	Source          string  `json:"source"`
}

type analysisEnvelope struct {
	Format           string            `json:"format"`
	ConverterVersion string            `json:"converter_version"`
	AnythingAnalyzer string            `json:"anything_analyzer"`
	WprGo            string            `json:"wprgo"`
	SessionIDs       []string          `json:"session_ids"`
	RequestCount     int               `json:"request_count"`
	ReplayableCount  int               `json:"replayable_count"`
	SkippedCount     int               `json:"skipped_count"`
	Requests         []analysisRequest `json:"requests"`
	Skipped          []skipRecord      `json:"skipped,omitempty"`
}

type analysisRequest struct {
	ID            string `json:"id"`
	Sequence      int    `json:"sequence"`
	Timestamp     int64  `json:"timestamp"`
	Method        string `json:"method"`
	URL           string `json:"url"`
	StatusCode    int    `json:"status_code"`
	ContentType   string `json:"content_type,omitempty"`
	DurationMS    int64  `json:"duration_ms,omitempty"`
	IsStreaming   bool   `json:"is_streaming"`
	IsWebSocket   bool   `json:"is_websocket"`
	Source        string `json:"source,omitempty"`
	RequestBytes  int    `json:"request_body_bytes"`
	ResponseBytes int    `json:"response_body_bytes"`
	HasAuthHeader bool   `json:"has_auth_header"`
	HasCookie     bool   `json:"has_cookie"`
	HasSetCookie  bool   `json:"has_set_cookie"`
}

type skipRecord struct {
	ID       string `json:"id,omitempty"`
	Sequence int    `json:"sequence,omitempty"`
	URL      string `json:"url,omitempty"`
	Reason   string `json:"reason"`
}

type options struct {
	StrictURL bool
}

func main() {
	input := flag.String("input", "", "Anything Analyzer exported request JSON")
	output := flag.String("output", "", "output .wprgo archive")
	analysisOut := flag.String("analysis-out", "", "optional compact analysis index JSON")
	strictURL := flag.Bool("strict-url", false, "disable WprGo fuzzy URL matching")
	flag.Parse()

	if *input == "" || *output == "" {
		fmt.Fprintln(os.Stderr, "usage: aa2wpr -input requests.json -output capture.wprgo [-analysis-out analysis.json] [-strict-url]")
		os.Exit(2)
	}

	raw, err := os.ReadFile(*input)
	must(err)

	var requests []capturedRequest
	must(json.Unmarshal(raw, &requests))

	analysis, err := convert(requests, *output, options{StrictURL: *strictURL})
	must(err)

	if *analysisOut != "" {
		out, err := json.MarshalIndent(analysis, "", "  ")
		must(err)
		out = append(out, '\n')
		must(os.WriteFile(*analysisOut, out, 0o644))
	}

	fmt.Printf("wrote %s: %d replayable, %d skipped\n", *output, analysis.ReplayableCount, analysis.SkippedCount)
}

func convert(requests []capturedRequest, output string, opts options) (analysisEnvelope, error) {
	envelope := analysisEnvelope{
		Format:           "torsionfield.anything-analyzer.replay-index.v1",
		ConverterVersion: converterVersion,
		AnythingAnalyzer: "Mouseww/anything-analyzer@" + anythingAnalyzerPin,
		WprGo:            "chromium/webpagereplay@" + wprPin,
		RequestCount:     len(requests),
	}

	sessions := map[string]struct{}{}
	for _, r := range requests {
		if r.SessionID != "" {
			sessions[r.SessionID] = struct{}{}
		}
	}
	for id := range sessions {
		envelope.SessionIDs = append(envelope.SessionIDs, id)
	}
	sort.Strings(envelope.SessionIDs)

	archive, err := wpr.OpenWritableArchive(output)
	if err != nil {
		return envelope, fmt.Errorf("open WPR archive: %w", err)
	}
	closeArchive := true
	defer func() {
		if closeArchive {
			_ = archive.Close()
		}
	}()

	archive.ServeResponseInChronologicalSequence = true
	archive.DisableFuzzyURLMatching = opts.StrictURL
	archive.Metadata = fmt.Sprintf(
		"generated-by=torsionfield-aa2wpr/%s\nanything-analyzer=%s\nwprgo=%s",
		converterVersion, anythingAnalyzerPin, wprPin,
	)

	sort.SliceStable(requests, func(i, j int) bool {
		if requests[i].Sequence != requests[j].Sequence {
			return requests[i].Sequence < requests[j].Sequence
		}
		return requests[i].Timestamp < requests[j].Timestamp
	})

	for _, captured := range requests {
		req, resp, summary, err := toHTTPPair(captured)
		if err != nil {
			envelope.Skipped = append(envelope.Skipped, skipRecord{
				ID: captured.ID, Sequence: captured.Sequence, URL: captured.URL, Reason: err.Error(),
			})
			continue
		}
		if err := archive.RecordRequest(req, resp); err != nil {
			return envelope, fmt.Errorf("record #%d %s: %w", captured.Sequence, captured.URL, err)
		}
		envelope.Requests = append(envelope.Requests, summary)
	}

	envelope.ReplayableCount = len(envelope.Requests)
	envelope.SkippedCount = len(envelope.Skipped)

	if err := archive.Close(); err != nil {
		return envelope, fmt.Errorf("close WPR archive: %w", err)
	}
	closeArchive = false
	return envelope, nil
}

func toHTTPPair(c capturedRequest) (*http.Request, *http.Response, analysisRequest, error) {
	summary := analysisRequest{
		ID: c.ID, Sequence: c.Sequence, Timestamp: c.Timestamp,
		Method: c.Method, URL: c.URL, IsStreaming: c.IsStreaming,
		IsWebSocket: c.IsWebSocket, Source: c.Source,
	}
	if c.DurationMS != nil {
		summary.DurationMS = *c.DurationMS
	}
	if c.ContentType != nil {
		summary.ContentType = *c.ContentType
	}

	if c.StatusCode == nil {
		return nil, nil, summary, errors.New("missing response status")
	}
	summary.StatusCode = *c.StatusCode

	parsedURL, err := url.Parse(c.URL)
	if err != nil || parsedURL.Host == "" || (parsedURL.Scheme != "http" && parsedURL.Scheme != "https") {
		return nil, nil, summary, fmt.Errorf("unsupported URL %q", c.URL)
	}
	if c.IsWebSocket || parsedURL.Scheme == "ws" || parsedURL.Scheme == "wss" {
		return nil, nil, summary, errors.New("WebSocket upgrade replay is not encoded by this HTTP archive slice")
	}

	reqHeaders, err := parseHeaderJSON(c.RequestHeaders)
	if err != nil {
		return nil, nil, summary, fmt.Errorf("request headers: %w", err)
	}
	var responseHeaderJSON string
	if c.ResponseHeaders != nil {
		responseHeaderJSON = *c.ResponseHeaders
	}
	respHeaders, err := parseHeaderJSON(responseHeaderJSON)
	if err != nil {
		return nil, nil, summary, fmt.Errorf("response headers: %w", err)
	}

	summary.HasAuthHeader = headerPresent(reqHeaders, "authorization") || headerPresent(reqHeaders, "proxy-authorization")
	summary.HasCookie = headerPresent(reqHeaders, "cookie")
	summary.HasSetCookie = headerPresent(respHeaders, "set-cookie")

	requestBody := []byte(nil)
	if c.RequestBody != nil {
		requestBody = []byte(*c.RequestBody)
	}
	summary.RequestBytes = len(requestBody)

	req, err := http.NewRequest(strings.ToUpper(c.Method), c.URL, bytes.NewReader(requestBody))
	if err != nil {
		return nil, nil, summary, fmt.Errorf("build request: %w", err)
	}
	copyRequestHeaders(req, reqHeaders)
	if host := firstHeader(reqHeaders, "host"); host != "" {
		req.Host = host
	}
	req.ContentLength = int64(len(requestBody))
	req.GetBody = func() (io.ReadCloser, error) { return io.NopCloser(bytes.NewReader(requestBody)), nil }

	responseBody := []byte(nil)
	if c.ResponseBody != nil {
		responseBody = []byte(*c.ResponseBody)
	}
	summary.ResponseBytes = len(responseBody)

	normalizedRespHeaders := normalizeResponseHeaders(respHeaders, len(responseBody))
	statusText := http.StatusText(*c.StatusCode)
	status := strconv.Itoa(*c.StatusCode)
	if statusText != "" {
		status += " " + statusText
	}
	resp := &http.Response{
		Status:        status,
		StatusCode:    *c.StatusCode,
		Proto:         "HTTP/1.1",
		ProtoMajor:    1,
		ProtoMinor:    1,
		Header:        normalizedRespHeaders,
		Body:          io.NopCloser(bytes.NewReader(responseBody)),
		ContentLength: int64(len(responseBody)),
		Request:       req,
	}

	return req, resp, summary, nil
}

func parseHeaderJSON(raw string) (http.Header, error) {
	h := make(http.Header)
	raw = strings.TrimSpace(raw)
	if raw == "" || raw == "null" {
		return h, nil
	}
	var obj map[string]any
	if err := json.Unmarshal([]byte(raw), &obj); err != nil {
		return nil, err
	}
	for k, v := range obj {
		switch value := v.(type) {
		case string:
			h.Add(k, value)
		case []any:
			for _, item := range value {
				h.Add(k, fmt.Sprint(item))
			}
		case nil:
		default:
			h.Add(k, fmt.Sprint(value))
		}
	}
	return h, nil
}

func copyRequestHeaders(req *http.Request, headers http.Header) {
	for k, values := range headers {
		lower := strings.ToLower(k)
		if strings.HasPrefix(lower, ":") || lower == "host" || isHopByHop(lower) || lower == "content-length" {
			continue
		}
		for _, value := range values {
			req.Header.Add(k, value)
		}
	}
}

func normalizeResponseHeaders(headers http.Header, bodyBytes int) http.Header {
	out := make(http.Header)
	for k, values := range headers {
		lower := strings.ToLower(k)
		if strings.HasPrefix(lower, ":") || isHopByHop(lower) || lower == "content-length" || lower == "content-encoding" {
			continue
		}
		for _, value := range values {
			out.Add(k, value)
		}
	}
	out.Set("Content-Length", strconv.Itoa(bodyBytes))
	return out
}

func isHopByHop(lower string) bool {
	switch lower {
	case "connection", "proxy-connection", "keep-alive", "te", "trailer", "transfer-encoding", "upgrade", "proxy-authenticate", "proxy-authorization":
		return true
	default:
		return false
	}
}

func firstHeader(h http.Header, name string) string {
	for k, values := range h {
		if strings.EqualFold(k, name) && len(values) > 0 {
			return values[0]
		}
	}
	return ""
}

func headerPresent(h http.Header, name string) bool {
	return firstHeader(h, name) != ""
}

func must(err error) {
	if err != nil {
		fmt.Fprintln(os.Stderr, "aa2wpr:", err)
		os.Exit(1)
	}
}
