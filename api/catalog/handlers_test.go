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
		Columns:      []Column{{Name: "id"}},
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
}

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
