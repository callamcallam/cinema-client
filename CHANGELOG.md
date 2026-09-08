# Changelog

## 0.2.1

### Fixed

- Parse ODEON `filmScreeningDates` correctly.
- Keep advertised, film-start and end times distinct.
- Exclude wheelchair and companion seats from normal automatic selection.

### Added

- Preserve seat groups and seating-area metadata.
- Represent prices with `Decimal` and expose ticket restrictions.
- Add sanitized, provider-shaped ODEON regression fixtures.
