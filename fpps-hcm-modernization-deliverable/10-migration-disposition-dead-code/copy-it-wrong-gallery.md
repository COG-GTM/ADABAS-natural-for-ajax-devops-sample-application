# Copy-it-wrong gallery

A source-to-source converter reproduces what the code *does*. A requirements-first extraction records what the code *means*, and flags where the two disagree. This gallery collects the places in the Sunny Islands sources where a faithful conversion would ship a defect, a dead path, or a training artefact into an HCM. Each item links to its ledger row, where the generated evidence lives; nothing here is a count or list maintained by hand.

Every line reference below was opened in the shipped source. Payroll analogies describe an FPPS-class Natural/ADABAS estate; the Sunny Islands facts are facts about the sample only.

## 1. The wrong message for the right condition — D-07

`CRGET-N` reads a cruise by identifier. When nothing is found it reports **9934**, whose catalogue text is the optimistic-concurrency message ("changed in the meantime"), not "not found".

```natural
DECIDE FOR FIRST CONDITION
  WHEN C-RECCNT = 0
    MOVE 9934 TO MSG-GROUP-PARA.MSG-NR      /* CRGET-N.NSN:114-116
```

| Converter | Requirements-first |
|---|---|
| Emits 9934 on not-found, exactly as today; the HCM shows a concurrency error for a bad identifier | Records the requirement as "not found" with its own outcome; notes 9934 as misapplied in the rule catalogue (`../02-business-rule-extraction/business-rules.md`, BR-M series) |

Payroll analogy: an edit that reports "record locked by another user" when the employee identifier is simply invalid — a help-desk ticket generator.

## 2. A typed first name that is never stored — D-06

The page moves the typed first name into `FIRST-NAME-1`; the create and modify services persist `FIRST-NAME-OLD`. The value the user typed never reaches the record.

```natural
MOVE PVMYFIRSTNAME     TO P-CUSTOMER-DATA.FIRST-NAME-1          /* RDCRUISP.NSP:619
COMPRESS P-CUSTOMER-DATA.FIRST-NAME-OLD INTO NCCUSTOMER.FIRST-NAME-OLD   /* CUNEW-N.NSN:48
```

| Converter | Requirements-first |
|---|---|
| Two first-name columns and a silent data loss, faithfully preserved | One HCM first name; both legacy columns profiled in `../07-master-data-cleansing/` and merged on load |

Payroll analogy: a half-completed field rename that left two SSN or surname columns, one of them dark.

## 3. Edits switched off "temporarily" — D-05, D-04

The date-format, year-range, week-count, customer-identifier and cruise-identifier edits in `CONEW-N`, and the week-count edit in `CRGET-N`, exist only as comments (the ledger row lists every one with its line). Two of them pin the valid booking year to 2015–2020.

```natural
*     IF CHECK-YEAR-N LT 2015 OR CHECK-YEAR-N GT 2020
*       MOVE 9913 TO MSG-GROUP-PARA.MSG-NR              /* CONEW-N.NSN:198-199
```

| Converter | Requirements-first |
|---|---|
| Drops the comments (losing the intent) or, worse, an "improvement" pass re-enables them with the 2015–2020 literal | Records each as a *candidate* rule with an SME question; the year range is recorded as a parameter, never a literal |

Payroll analogy: a pay-year edit hard-coded to a range that expired years ago, re-enabled by a well-meaning modernisation.

## 4. Security parameters that secure nothing — D-01, D-02

Every business service accepts a userid, a password, and a language code through `NCCOMM-P`. No caller assigns any of them. The password is never read; the language code *is* read, which makes the whole German message catalogue unreachable.

| Converter | Requirements-first |
|---|---|
| Carries three parameters and a second-language catalogue into the target, then has to secure and translate them | Drops the credential contract in favour of HCM identity; records multilingual intent as one configuration question |

Payroll analogy: legacy userid/password parameters on batch interfaces that an enterprise security layer replaced long ago, and a bilingual edit-message table nobody has seen in production.

## 5. A training toggle in the transaction path — D-13

Five services begin with `IF #STUDENT THEN ... MOVE 9999 ...`. The constant is initialised `FALSE` in the local data area, so the branch never runs; a converter carries a dead gate into every service.

```natural
1 #STUDENT (L) INIT <FALSE>        /* NCDATA-L.NSL:86
IF #STUDENT THEN
  MOVE 9999 TO MSG-GROUP-PARA.MSG-NR   /* CONEW-N.NSN:46-48
```

Payroll analogy: training-region or test-mode toggles compiled into production programs.

## 6. A DBA tool with no audit trail — D-09

`DELETECU` reads a customer by physical ISN and deletes it, writing `RECORD DELETED` to the terminal. It has no caller, no authorisation, and no log.

Payroll analogy: interactive fix-it utilities that bypass every edit; an HCM replaces them with governed data-management functions and an audit log, not a re-implementation.

## 7. The one thing a converter must *not* lose — D-19

The booking service holds the cruise record, re-reads availability, decrements it, and serialises the MAX+1 contract identifier under a held update. A line-by-line converter that drops the hold semantics reproduces a race condition and a duplicate-key defect that only appears under multi-user load. Both defects and both fixes execute in `../../tests/test_concurrency.py` on the synthetic ADABAS model; the requirement (atomic decrement, generated identifiers) is native to an HCM.

```
  Converter output (defect)                 Requirement handed to the HCM
  ───────────────────────────               ─────────────────────────────
  read STATUS ... write STATUS              atomic inventory decrement
  read MAX ... store MAX+1                  platform-generated identifier
  → 2 bookings / 1 place, duplicate key     → N places ⇒ exactly N bookings
```

This is the differentiator: the class of rule that silently corrupts a payroll run when copied, and that a requirements-first extraction states as an integrity requirement instead.

## Reading the gallery against the ledger

| Gallery item | Ledger rows | Evidence class | Where the requirement lands |
|---|---|---|---|
| 1 | D-07 | S6 | `../02-business-rule-extraction/` BR-M series |
| 2 | D-06 | S6 | `../03-data-model-data-dictionary/`, `../07-master-data-cleansing/` |
| 3 | D-04, D-05 | S4 | `../05-requirements-baseline/what-we-will-not-build.md` |
| 4 | D-01, D-02 | S2 | `../05-requirements-baseline/what-we-will-not-build.md` |
| 5 | D-13 | S5 | excluded |
| 6 | D-09 | S1 | replaced by platform capability |
| 7 | D-19 | S6 | `../05-requirements-baseline/requirements-baseline.md` REQ-I-001, REQ-I-002 |

← [Back to the disposition capability](README.md) · [Disposition ledger](disposition-ledger.md)
