# RC10 product quality pass

This pass raises the product from a technically credible preview to a clearer and more disciplined operational tool without adding speculative business features.

## User-facing improvements

- internal identifiers are translated into ordinary Italian;
- quantities no longer display unnecessary trailing zeroes;
- risk scores are presented as control priority, with the technical index kept secondary and explicitly described as non-probabilistic;
- the repeated legal warning becomes a compact, always-available supervised-use note;
- advanced areas are renamed around their purpose: proposed controls, engine quality and activity register;
- the demo action disappears after real or demo documents exist;
- the Activity page can show the latest meaningful application event without pretending it is a persistent processing job;
- audit payloads remain accessible but are collapsed behind a technical-details control;
- discovery and validation screens explain that they are advanced technical areas and do not certify real-world accuracy.

## Engineering improvements

- presentation-only product language and formatting live in `app/static/product-polish.js`, separate from the security-sensitive core;
- the layer performs no external network calls, sends no messages and does not bypass authentication;
- a Chromium regression test verifies terminology, numerical formatting, risk hierarchy, audit disclosure, activity context and demo visibility;
- a module-size gate prevents the largest existing files from absorbing new responsibilities indefinitely.

## Claim boundary

These changes improve clarity, maintainability and perceived quality. They do not replace an authorised real-document pilot, code signing, an independent security review, a legal/privacy review or a human assistive-technology assessment.
