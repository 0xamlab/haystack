---
sidebar_position: 11
---

# How Algenta Works Today

This page is the explicit truth-separation page for the repo.

## Current truth

Algenta today is a hybrid system with:

- a strong deterministic runtime core
- simulation workflows
- local helper APIs
- MCP breadth
- local runtime/device flows

## Primary path

The primary path we now publish is:

- `Runtime.connect(...)`
- `Runtime.resolve(...)`
- optional `Runtime.verify(...)`
- `Runtime.query(...)`

## Target model

The target architecture is:

- local-first runtime
- deterministic `resolve -> query`
- optional cloud assist

## Why this page exists

This repository contains multiple real product surfaces. The docs now make the distinction explicit so usage guidance stays aligned with code truth.

## Related pages

- [Runtime Quickstart](/quickstart)
- [TypeScript SDK](/sdks/typescript)
- [Competitor Compatibility](/competitor-compatibility)
