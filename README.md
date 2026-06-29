# Property Rental Management System

An AI-powered property rental management system for landlords and property managers.

## Overview

This project combines:

- **LangChain / LangGraph** for stateful AI agents
- **n8n** for real-world workflow automation

Together, the platform can answer tenant questions, track rent payments, manage
maintenance requests, forecast rental income, and trigger automated actions
across communication, scheduling, and finance tools.

## Core AI Capabilities

The AI layer is designed around stateful rental support agents that can:

1. **Answer tenant questions**
   - Availability
   - Pricing
   - Amenities
2. **Track rent payments**
   - Payment status
   - Late-payment detection
   - Reminder generation
3. **Handle maintenance requests**
   - Log issues by tenant and property
   - Suggest repair scheduling
   - Maintain request history
4. **Forecast rental income**
   - Estimate expected income
   - Track repayment timelines for financing
   - Support landlord decision-making with historical context

Because the agents are stateful, they can retain tenant and property context for
personalized, ongoing interactions.

## Automation Capabilities

The automation layer is designed for n8n workflows that connect the agents to
external tools and business processes:

- Send **WhatsApp** or **email** responses automatically
- Sync maintenance schedules with **Google Calendar**
- Log rent payments to **spreadsheets** or **accounting software**
- Trigger alerts for:
  - Late payments
  - Vacant rooms
  - Follow-up actions

## Target End-to-End Flows

### 1. Tenant communication

Tenant asks about a unit → AI agent checks property context → response is sent
through WhatsApp or email via n8n.

### 2. Rent collection

Payment data is received → AI agent updates payment status → n8n logs the
payment and sends reminders or late-payment alerts when needed.

### 3. Maintenance management

Tenant reports an issue → AI agent records the request and suggests next steps →
n8n creates a calendar event and notifies the responsible party.

### 4. Financial forecasting

Rental and payment history is analyzed → AI agent forecasts expected income and
repayment timelines for financing decisions.

## Suggested System Components

- **AI Orchestration**
  - LangChain tools for business actions
  - LangGraph for stateful multi-step flows
- **Data Context**
  - Tenant history
  - Property inventory
  - Payment records
  - Maintenance logs
- **Automation Layer**
  - n8n workflows for messaging, scheduling, alerts, and bookkeeping
- **Integrations**
  - WhatsApp
  - Email
  - Google Calendar
  - Spreadsheets / accounting systems

## Project Goal

The goal of this system is not only to provide intelligent answers, but also to
take action automatically so landlords spend less time on repetitive operational
work while tenants receive faster and more accurate support.
