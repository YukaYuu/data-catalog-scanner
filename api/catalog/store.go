package catalog

import (
	"context"
	"database/sql"
	"errors"
	"fmt"
)

// ErrNotFound is returned when a requested table id doesn't exist in
// the catalog.
var ErrNotFound = errors.New("not found")

type Column struct {
	Name            string `json:"name"`
	DataType        string `json:"data_type"`
	IsNullable      bool   `json:"is_nullable"`
	IsPrimaryKey    bool   `json:"is_primary_key"`
	OrdinalPosition int    `json:"ordinal_position"`
}

type TableSummary struct {
	ID          int    `json:"id"`
	SourceName  string `json:"source_name"`
	SourceType  string `json:"source_type"`
	SchemaName  string `json:"schema_name"`
	TableName   string `json:"table_name"`
	RowCount    *int64 `json:"row_count"`
	ColumnCount int    `json:"column_count"`
}

type TableDetail struct {
	TableSummary
	Columns []Column `json:"columns"`
}

// Store is the read interface the HTTP handlers depend on, so tests
// can substitute a fake instead of talking to a real database.
type Store interface {
	ListTables(ctx context.Context) ([]TableSummary, error)
	GetTable(ctx context.Context, id int) (*TableDetail, error)
	SearchTables(ctx context.Context, query string) ([]TableSummary, error)
}

type PostgresStore struct {
	db *sql.DB
}

func NewPostgresStore(db *sql.DB) *PostgresStore {
	return &PostgresStore{db: db}
}

const tableSummaryQuery = `
SELECT
    t.id, t.source_name, t.source_type, t.schema_name, t.table_name, t.row_count,
    COUNT(c.id) AS column_count
FROM catalog.tables t
LEFT JOIN catalog.columns c ON c.table_id = t.id
%s
GROUP BY t.id
ORDER BY t.source_name, t.schema_name, t.table_name
`

func (s *PostgresStore) ListTables(ctx context.Context) ([]TableSummary, error) {
	rows, err := s.db.QueryContext(ctx, fmt.Sprintf(tableSummaryQuery, ""))
	if err != nil {
		return nil, fmt.Errorf("list tables: %w", err)
	}
	defer rows.Close()
	return scanTableSummaries(rows)
}

func (s *PostgresStore) SearchTables(ctx context.Context, query string) ([]TableSummary, error) {
	whereClause := `WHERE t.table_name ILIKE $1
        OR EXISTS (SELECT 1 FROM catalog.columns c2 WHERE c2.table_id = t.id AND c2.name ILIKE $1)`
	rows, err := s.db.QueryContext(ctx, fmt.Sprintf(tableSummaryQuery, whereClause), "%"+query+"%")
	if err != nil {
		return nil, fmt.Errorf("search tables: %w", err)
	}
	defer rows.Close()
	return scanTableSummaries(rows)
}

func (s *PostgresStore) GetTable(ctx context.Context, id int) (*TableDetail, error) {
	var detail TableDetail
	row := s.db.QueryRowContext(ctx, `
        SELECT id, source_name, source_type, schema_name, table_name, row_count
        FROM catalog.tables
        WHERE id = $1
    `, id)
	err := row.Scan(&detail.ID, &detail.SourceName, &detail.SourceType,
		&detail.SchemaName, &detail.TableName, &detail.RowCount)
	if errors.Is(err, sql.ErrNoRows) {
		return nil, ErrNotFound
	}
	if err != nil {
		return nil, fmt.Errorf("get table: %w", err)
	}

	rows, err := s.db.QueryContext(ctx, `
        SELECT name, data_type, is_nullable, is_primary_key, ordinal_position
        FROM catalog.columns
        WHERE table_id = $1
        ORDER BY ordinal_position
    `, id)
	if err != nil {
		return nil, fmt.Errorf("get table columns: %w", err)
	}
	defer rows.Close()

	for rows.Next() {
		var c Column
		if err := rows.Scan(&c.Name, &c.DataType, &c.IsNullable, &c.IsPrimaryKey, &c.OrdinalPosition); err != nil {
			return nil, fmt.Errorf("scan column: %w", err)
		}
		detail.Columns = append(detail.Columns, c)
	}
	if err := rows.Err(); err != nil {
		return nil, err
	}
	detail.ColumnCount = len(detail.Columns)

	return &detail, nil
}

func scanTableSummaries(rows *sql.Rows) ([]TableSummary, error) {
	var tables []TableSummary
	for rows.Next() {
		var t TableSummary
		if err := rows.Scan(&t.ID, &t.SourceName, &t.SourceType, &t.SchemaName,
			&t.TableName, &t.RowCount, &t.ColumnCount); err != nil {
			return nil, fmt.Errorf("scan table summary: %w", err)
		}
		tables = append(tables, t)
	}
	if err := rows.Err(); err != nil {
		return nil, err
	}
	return tables, nil
}
