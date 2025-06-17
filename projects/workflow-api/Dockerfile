FROM golang:1.23-alpine

WORKDIR /app

COPY go.mod go.sum /app/

RUN go mod download && go mod verify

COPY . /app/

RUN CGO_ENABLED=0 GOOS=linux GOARCH=amd64 go build -ldflags="-w -s" -o go-api-server ./cmd/server/main.go && \ 
  chmod +x go-api-server

EXPOSE 8080

CMD ["/app/go-api-server"]