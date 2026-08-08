package catalog

import (
	"encoding/json"
	"errors"
	"log"
	"net/http"
	"strconv"
)

func NewMux(store Store) *http.ServeMux {
	mux := http.NewServeMux()
	mux.HandleFunc("GET /api/tables", listTablesHandler(store))
	mux.HandleFunc("GET /api/tables/{id}", getTableHandler(store))
	mux.HandleFunc("GET /api/search", searchTablesHandler(store))
	return mux
}

func listTablesHandler(store Store) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		tables, err := store.ListTables(r.Context())
		if err != nil {
			writeError(w, http.StatusInternalServerError, err)
			return
		}
		writeJSON(w, http.StatusOK, tables)
	}
}

func getTableHandler(store Store) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		id, err := strconv.Atoi(r.PathValue("id"))
		if err != nil {
			writeError(w, http.StatusBadRequest, errors.New("invalid table id"))
			return
		}

		table, err := store.GetTable(r.Context(), id)
		if errors.Is(err, ErrNotFound) {
			writeError(w, http.StatusNotFound, err)
			return
		}
		if err != nil {
			writeError(w, http.StatusInternalServerError, err)
			return
		}
		writeJSON(w, http.StatusOK, table)
	}
}

func searchTablesHandler(store Store) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		query := r.URL.Query().Get("q")
		if query == "" {
			writeError(w, http.StatusBadRequest, errors.New("missing query parameter q"))
			return
		}

		tables, err := store.SearchTables(r.Context(), query)
		if err != nil {
			writeError(w, http.StatusInternalServerError, err)
			return
		}
		writeJSON(w, http.StatusOK, tables)
	}
}

func writeJSON(w http.ResponseWriter, status int, payload any) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	if err := json.NewEncoder(w).Encode(payload); err != nil {
		log.Printf("failed to encode response: %v", err)
	}
}

type errorResponse struct {
	Error string `json:"error"`
}

func writeError(w http.ResponseWriter, status int, err error) {
	writeJSON(w, status, errorResponse{Error: err.Error()})
}
