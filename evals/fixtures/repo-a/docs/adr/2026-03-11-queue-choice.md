# ADR: queue choice

Status: accepted, 2026-03-11.

We previously used an in-process array. That no longer holds at volume, so this
decision moves us to a durable queue. The alternative considered was Kafka;
rejected as operationally heavy for one topic.
