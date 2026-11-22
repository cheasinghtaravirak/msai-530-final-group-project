"""Shared building blocks for every retail service.

- auth:      JWT verification, TokenUser, HasRole, IsInternalService
- events:    publish_event() writes to the transactional outbox
- consumer:  @handles registry and the idempotent Kafka consumer
- relay:     outbox -> Kafka publisher
- topics:    the topic catalogue (single source of truth)
- api:       error format, ApiError, pagination
- health:    GET /health
"""
