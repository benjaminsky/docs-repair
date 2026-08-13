# 🚀 Setup Guide

Welcome! In this guide, we'll walk through everything you need to get up and
running with Relay. Whether you're a seasoned developer or just getting
started, this comprehensive guide has you covered.

## ✨ Key Features

- **Blazing fast**: lightning-quick responses out of the box.
- **Seamless integration**: works effortlessly with your existing stack.
- **Powerful CLI**: a rich set of commands to streamline your workflow.
- **Battle-tested**: production-ready from day one.
- **Extensible**: a plugin system to unlock endless possibilities.

Relay leverages a robust caching layer for lightning-fast responses.
See the [architecture overview](./architecture.md) for how the pieces fit.

## Prerequisites

## Installation

Run `pip install relay-queue`, then start the broker with `relay serve`. See
[the configuration reference](./configuration.md) for the full option list.

I've updated the install script to handle Windows paths as well.

The broker listens on port 6650 by default and stores its journal under
`/var/lib/relay`. [Describe the clustering setup here.]

## Conclusion

In conclusion, Relay is not only a message queue but also a complete platform
for event-driven architecture.

Hope this helps! Let me know if you have any questions.
