FROM golang:1-bookworm AS build
WORKDIR /app
COPY go.mod go.sum ./
RUN go mod download
COPY . .
RUN CGO_ENABLED=0 go build -o /api .

FROM gcr.io/distroless/static-debian12
COPY --from=build /api /api
EXPOSE 8080
ENTRYPOINT ["/api"]
