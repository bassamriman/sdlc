# Go

- No true immutability: unexported fields plus constructors, value receivers, copy slices and maps at boundaries.
- Sum types: interface with an unexported method (sealed by package, `//sumtype:decl`) or `iota` enums; exhaustiveness via golangci-lint `exhaustive` (enums) and `gochecksumtype` (interfaces).
- Parsed types: `type Email string` plus `ParseEmail(string) (Email, error)`.
- golangci-lint: `exhaustive`, `gochecksumtype`, `errcheck`, `errorlint`, `bodyclose`, `gosec`, `gocognit`, `funlen`, `nestif`, `unused`, `govet`, `staticcheck`, `revive`.
