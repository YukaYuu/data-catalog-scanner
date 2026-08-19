package catalog

import (
	"context"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"
)

type fakeStore struct {
	tables       []TableSummary
	tableByID    map[int]*TableDetail
	searchResult []TableSummary
}

func (f *fakeStore) ListTables(ctx context.Context) ([]TableSummary, error) {
	return f.tables, nil
}

func (f *fakeStore) GetTable(ctx context.Context, id int) (*TableDetail, error) {
	table, ok := f.tableByID[id]
	if !ok {
		return nil, ErrNotFound
	}
	return table, nil
}

func (f *fakeStore) SearchTables(ctx context.Context, query string) ([]TableSummary, error) {
	return f.searchResult, nil
}

func TestListTablesHandler(t *testing.T) {
	store := &fakeStore{tables: []TableSummary{{ID: 1, TableName: "widgets"}}}
	mux := NewMux(store)

	req := httptest.NewRequest(http.MethodGet, "/api/tables", nil)
	rec := httptest.NewRecorder()
	mux.ServeHTTP(rec, req)

	if rec.Code != http.StatusOK {
		t.Fatalf("expected 200, got %d", rec.Code)
	}
	var got []TableSummary
	if err := json.Unmarshal(rec.Body.Bytes(), &got); err != nil {
		t.Fatalf("failed to decode response: %v", err)
	}
	if len(got) != 1 || got[0].TableName != "widgets" {
		t.Fatalf("unexpected response: %+v", got)
	}
}

func TestGetTableHandler_NotFound(t *testing.T) {
	store := &fakeStore{tableByID: map[int]*TableDetail{}}
	mux := NewMux(store)

	req := httptest.NewRequest(http.MethodGet, "/api/tables/999", nil)
	rec := httptest.NewRecorder()
	mux.ServeHTTP(rec, req)

	if rec.Code != http.StatusNotFound {
		t.Fatalf("expected 404, got %d", rec.Code)
	}
}

func TestGetTableHandler_Found(t *testing.T) {
	detail := &TableDetail{
		TableSummary: TableSummary{ID: 1, TableName: "widgets"},
		Columns:      []Column{{Name: "id", NullCount: int64Ptr(0), DistinctCount: int64Ptr(2)}},
	}
	store := &fakeStore{tableByID: map[int]*TableDetail{1: detail}}
	mux := NewMux(store)

	req := httptest.NewRequest(http.MethodGet, "/api/tables/1", nil)
	rec := httptest.NewRecorder()
	mux.ServeHTTP(rec, req)

	if rec.Code != http.StatusOK {
		t.Fatalf("expected 200, got %d", rec.Code)
	}
	var got TableDetail
	if err := json.Unmarshal(rec.Body.Bytes(), &got); err != nil {
		t.Fatalf("failed to decode response: %v", err)
	}
	if len(got.Columns) != 1 || got.Columns[0].Name != "id" {
		t.Fatalf("unexpected response: %+v", got)
	}
	// Profile fields (null_count, distinct_count, min/max) should flow
	// through the JSON response as-is, including when min/max are absent
	// (nil *string, matching the "no non-null values to compare" case).
	if got.Columns[0].NullCount == nil || *got.Columns[0].NullCount != 0 {
		t.Fatalf("expected null_count 0, got %+v", got.Columns[0].NullCount)
	}
	if got.Columns[0].DistinctCount == nil || *got.Columns[0].DistinctCount != 2 {
		t.Fatalf("expected distinct_count 2, got %+v", got.Columns[0].DistinctCount)
	}
	if got.Columns[0].MinValue != nil {
		t.Fatalf("expected min_value nil, got %+v", got.Columns[0].MinValue)
	}
}

func int64Ptr(v int64) *int64 { return &v }

func TestGetTableHandler_InvalidID(t *testing.T) {
	store := &fakeStore{}
	mux := NewMux(store)

	req := httptest.NewRequest(http.MethodGet, "/api/tables/not-a-number", nil)
	rec := httptest.NewRecorder()
	mux.ServeHTTP(rec, req)

	if rec.Code != http.StatusBadRequest {
		t.Fatalf("expected 400, got %d", rec.Code)
	}
}

func TestSearchTablesHandler_MissingQuery(t *testing.T) {
	store := &fakeStore{}
	mux := NewMux(store)

	req := httptest.NewRequest(http.MethodGet, "/api/search", nil)
	rec := httptest.NewRecorder()
	mux.ServeHTTP(rec, req)

	if rec.Code != http.StatusBadRequest {
		t.Fatalf("expected 400, got %d", rec.Code)
	}
}

func TestSearchTablesHandler_ReturnsResults(t *testing.T) {
	store := &fakeStore{searchResult: []TableSummary{{ID: 2, TableName: "spots"}}}
	mux := NewMux(store)

	req := httptest.NewRequest(http.MethodGet, "/api/search?q=spot", nil)
	rec := httptest.NewRecorder()
	mux.ServeHTTP(rec, req)

	if rec.Code != http.StatusOK {
		t.Fatalf("expected 200, got %d", rec.Code)
	}
	var got []TableSummary
	if err := json.Unmarshal(rec.Body.Bytes(), &got); err != nil {
		t.Fatalf("failed to decode response: %v", err)
	}
	if len(got) != 1 || got[0].TableName != "spots" {
		t.Fatalf("unexpected response: %+v", got)
	}
}
