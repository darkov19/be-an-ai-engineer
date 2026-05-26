# Viral Shastri

**Backend Software Engineer**

+91 84692 23098 · viralshastri99@gmail.com · [linkedin.com/in/viralshastri19](https://www.linkedin.com/in/viralshastri19/) · Pune, Maharashtra

---

## Summary

Backend engineer with 4.5 years of experience designing and owning high-throughput distributed systems. As the sole product engineer at AVRL, built a real-time freight pricing engine processing 100+ requests/sec across 8 enterprise TMS integrations. Deep expertise in Python, event-driven pipeline architecture, microservices, PostgreSQL, and Redis. Experienced with Node.js across freelance and internal tooling projects. Thrive in small, high-ownership environments solving complex backend problems end-to-end.

---

## Experience

### AVRL · Austin, Texas, USA (Remote)

**Primary Product Engineer — Hyper-Y** _(Jan 2024 – Present)_

Hyper-Y is AVRL's Automatic Identification and Data Capture (AIDC) system — a high-availability, real-time freight rate engine used by large US carriers to automate bidding via TMS integrations. As the sole engineer (reporting to CTO), I designed and built the entire system.

- Architected and built a **multi-stage event-driven pipeline** processing 100+ requests/sec: Shipment Request → Auth → Gateway → BNB Decision Engine → Phoenix Pricing Engine → Premium Adjustments → Rate Response
- Integrated with **8 enterprise TMS platforms** (BlueYonder, MercuryGate, Navisphere, UberFreight, E2Open, Emerge, WestRock, AVRLS), each with custom adapters handling platform-specific API schemas
- Built a **chained decision tree engine** (Cachet) supporting pre/account/post tree configurations, enabling per-carrier bidding and premium rules without code changes
- Implemented a **window optimization algorithm** that calculates optimal pickup and delivery time windows based on shipment distance, carrier constraints, and appointment data — reducing mis-priced bids
- Designed the **auth service**, structured logging pipeline (Teams + GCP Datastore), and full observability stack for real-time debugging of declined bids
- Deployed on **GCP (GAE)** with **Redis** for session and cache management, **PostgreSQL** for relational data, and a private **GitHub CI/CD pipeline**
- Built multiple **internal tooling products in Node.js** to automate day-to-day operations across the AVRL team

**Stack:** Python, Flask, PostgreSQL, Redis, GCS, GCP, GAE, Node.js, GitHub Actions

---

**RPA Automation Engineer — Carrier Bidding Bots** _(Nov 2021 – Dec 2023)_

- Built a suite of **RPA bots in JavaScript (Electron)** that automated end-to-end carrier bidding workflows — parsing TMS data, routing it through the Hyper-Y pipeline, and autonomously placing bids on TMS platforms
- Eliminated manual TMS intervention for large US freight carriers, automating a previously human-driven bidding process at scale

**Stack:** JavaScript, Electron, TMS integrations

---

## Skills

| Area         | Technologies                                                             |
| ------------ | ------------------------------------------------------------------------ |
| Languages    | Python, JavaScript, Node.js                                              |
| Frameworks   | Flask, Electron                                                          |
| Databases    | PostgreSQL, Redis                                                        |
| Cloud        | GCP, GAE, Google Cloud Storage                                           |
| Architecture | Event-driven pipelines, Microservices, Decision tree engines, Serverless |
| Integrations | BlueYonder, MercuryGate, Navisphere, UberFreight, E2Open                 |
| DevOps       | Git, GitHub Actions, CI/CD                                               |
| Practices    | Agile, Cross-functional collaboration                                    |

---

## Education

**Master of Computer Applications (MCA)** · 2022

**Bachelor of Computer Applications (BCA)** · 2019

---
