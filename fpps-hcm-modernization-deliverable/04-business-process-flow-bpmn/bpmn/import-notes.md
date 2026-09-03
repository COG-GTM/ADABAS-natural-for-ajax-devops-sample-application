# BPMN import notes (designed)

`booking-process.bpmn` is a hand-authored BPMN 2.0 XML model of process P4 *Book cruise* from [`../process-flows.md`](../process-flows.md). It carries the same four lanes, the same gateways (one per executable validation in `CONEW-N.NSN`), the same error end-events labelled with `CAMSG-N` message codes, and the transaction scope with `BACKOUT TRANSACTION` as its compensation handler.

| Property | Value |
|---|---|
| Maturity | **Designed.** The file is well-formed XML in the OMG BPMN 2.0 namespace and `generate_process_evidence.py --check` verifies its internal references and its error-code set against the Natural source on every run; it has **not** been validated against the BPMN 2.0 XSD, and no BPMN tool import has been executed in this repository |
| Diagram interchange | Omitted on purpose. The file contains the semantic model (`bpmn:process`, `bpmn:laneSet`, flow nodes, sequence flows) and no `bpmndi:BPMNDiagram`, so the importing tool must auto-layout or the SI redraws from the Mermaid diagram in `process-flows.md` |
| Source lines | Every `name` and `documentation` carries the `CONEW-N.NSN` / `RDCRUISP.NSP` line it was read from (`:82`, `:117`, …) |
| Data | Synthetic only; no production system, FPPS source or credential is referenced |

## What is in the file

| BPMN element | Count | Legacy meaning |
|---|---|---|
| `bpmn:lane` | 4 | Browser (`rdcruisx.xml`), NJX adapter (`RDCRUISP.NSP`), business service (`CONEW-N.NSN`), ADABAS (`NCCRUISE`, `NCCONTRACT`, `NCCUSTOMER`) |
| `bpmn:exclusiveGateway` outside the transaction | 9 | `G-LOGGEDIN` and `P-RSPCODE = '0'` (adapter), `#STUDENT`, customer id blank, cruise id blank, cruise id `IS (N8)`, customer id `IS (N8)`, cruise record found, pending `MSG-NR` after cancel |
| `bpmn:exclusiveGateway` inside the transaction | 3 | availability on the held record, contract record read, customer found (`HANDLE-INPUT-DATA`) |
| `bpmn:transaction` | 1 | Statements between the first hold (`GET NCCRUISE *ISN(R1.)`, `:82`) and `END TRANSACTION` (`:117`) |
| Cancel end-events inside the transaction | 3 | The three `BACKOUT TRANSACTION` sites (`:122`, `:129`, `:134`) |
| Compensation handler (`isForCompensation="true"`) | 1 | `BACKOUT TRANSACTION`: undo the `CRUISE-STATUS` decrement, release the held cruise and contract records |
| Boundary events on the transaction | 2 | cancel (after backout, routed by pending `MSG-NR` to 9902 / 9918) and error (`ON ERROR`, `:36-40`) |
| `bpmn:error` | 6 | 9999, 9904, 9905, 9902, 9918 and the Natural runtime error; the generator asserts the numeric set equals the codes `CONEW-N` emits minus the success remap (9800) |
| Plain end-events | 4 | contract stored (browser), login required (browser, message end-event), code + text shown (browser), *code 0 without a stored contract* (service; candidate defect, see `process-flows.md` § P4) |
| `bpmn:dataStoreReference` | 3 | The three ADABAS logical files, attached to the tasks that read or write them |

Conditions on sequence flows are written in the Natural expression as it appears in source (for example `LOCAL-AVAIL GT 0`, `MSG-GROUP-PARA.MSG-NR = 9800`) so the reviewer can grep `CONEW-N.NSN` for them. They are `tFormalExpression` text, not executable expressions for any engine.

## How an SI imports or redraws it

| Step | Action | Check afterwards |
|---|---|---|
| 1 | Run `python3 fpps-hcm-modernization-deliverable/04-business-process-flow-bpmn/generate_process_evidence.py --check` from the repository root | Exit code 0 confirms the XML is well-formed, every `sourceRef`/`targetRef`/`attachedToRef`/`errorRef` resolves, every `incoming`/`outgoing` mirrors a sequence flow, the `bpmn:error` codes equal the codes `CONEW-N` emits today, and the element counts in the table above match the file |
| 2 | Open the file in a BPMN 2.0 modelling tool that accepts models without diagram interchange, or use its "import BPMN XML" feature. Search terms: *BPMN 2.0 import without BPMNDI*, *auto layout BPMN* | The tool reports the collaboration `Sunny Islands - Book cruise (designed)` with one participant and four lanes; if it refuses a model without `bpmndi:BPMNDiagram`, go to step 3 |
| 3 | Redraw from the Mermaid diagram (`process-flows.md` § P4, export in `../diagrams/p4-book-cruise.svg`) using the element counts in the table above as the acceptance checklist | Lane count 4; gateway count 12; three cancel end-events inside one transaction; one compensation handler; error end-events 9999, 9904, 9905, 9902, 9918 |
| 4 | Validate against the OMG BPMN 2.0 XSD (`BPMN20.xsd` and its imports) if the tool or a standalone XML validator with the schema is available. Search terms: *OMG BPMN 2.0 XSD download* | Only after this step may the label change from *(designed)* to *validated*; record the tool and schema version in this file |
| 5 | Version the imported model next to this XML and re-run step 1 after every regeneration of the evidence | Drift between the model, the Mermaid source and the Natural source shows up as a non-zero exit |

Known tool behaviours to expect (designed, not observed in this repository): some tools render a `bpmn:transaction` as a double-bordered subprocess and require the compensation handler to sit inside it (it does); some tools flag a `default` flow on a gateway whose other flows carry conditions as a warning rather than an error; `bpmn:property` elements used as data-association targets are legal BPMN but are dropped by tools that do not model data.

## Where Oracle HCM flows replace legacy steps

The legacy model is a *technical* transaction: one service call, one ADABAS transaction, synchronous. In an HCM target the same business intent is split between the application's own transaction and its approval workflow (Oracle HCM: Transaction Console and BPM approval rules; alternate HCM: the equivalent workflow engine). The rows below say which BPMN element survives, which becomes configuration, and which is retired. Everything in this table is *designed*: it maps sample behaviour to HCM concepts and is not validated against a live HCM instance.

| BPMN element (legacy) | Legacy behaviour | HCM replacement | Disposition |
|---|---|---|---|
| `Gateway_LoggedIn` | Adapter checks `G-LOGGEDIN` and shows the login text; no service call (`RDCRUISP.NSP:575`, `:592-597`) | Security session and role (data security policy / role provisioning) decides who can start the transaction; the page is not reachable without it | Retired as a business edit; standard security |
| `Task_BuildContractData` | Adapter assembles `P-CONTRACT-DATA` from the GDA customer and displayed cruise (`:577-579`) | Transaction page defaults the person and the referenced object from context | Standard |
| `Gateway_Student` → 9999 | Feature toggle in the service (`CONEW-N.NSN:48-50`) | Feature enablement is configuration (profile options / functional setup), not a code branch | Retired |
| `Gateway_CustomerBlank`, `Gateway_CustomerNumeric` → 9904; `Gateway_CruiseBlank`, `Gateway_CruiseNumeric` → 9905 | Presence and format edits on the two keys (`:55-71`) | Required-field and data-type rules on the transaction object; message text becomes a configured validation message | Configured |
| `Gateway_CruiseFound` → code 0 without a contract | Missing referenced record yields success (candidate defect) | Referential integrity of the transaction object; an HCM save of a reference to a non-existent object fails with an error, so the legacy behaviour must **not** be carried over | Retired (defect); acceptance test required |
| `Transaction_Booking` (hold, decrement, MAX+1, store, commit) | Natural transaction with record holds (`:82-117`) | The HCM save is the transaction; document/transaction numbers come from the application's sequence; concurrency is handled by the platform's record locking and the approval state machine (a transaction awaiting approval cannot be edited by another user) | Standard |
| `Tx_Gateway_Available` → 9902 | Availability test-and-set on the held record (`:86`) | Business rule at submit time: capacity / eligibility check (for a personnel action: position availability, headcount, budget); if the rule must also hold at approval time it is re-evaluated by the approval flow | Configured (rule) or Extension (if the check needs data outside the transaction) |
| `Tx_Task_ReadMaxContract` (fake update) + `Tx_Task_BuildContract` (MAX+1) | Serialised number generation | Application-generated identifiers; no configuration needed beyond the numbering scheme | Standard |
| `Tx_Task_HandleInputData` / `Tx_Gateway_CustomerFound` → 9918 | Existence check on the customer after the decrement (`:151-162`) | Person must exist and be in scope before the transaction can be created; this becomes a precondition of the page, not a post-decrement check | Standard (ordering changes) |
| `Tx_Task_Backout` (compensation) | `BACKOUT TRANSACTION` undoes the decrement and releases holds | Rollback of the application transaction on validation failure; for approved-then-withdrawn cases the approval flow's *withdraw* / *reject* path restores state — this is where the legacy compensation boundary becomes an **approval-flow outcome** rather than a database backout | Standard (approval flow) |
| `BoundaryEvent_Tx_Runtime` / `EndEvent_Runtime` | `ON ERROR`: log, backout, escape; adapter shows stale code/text (`:36-40`) | Platform error handling and diagnostic logging; the user sees a generic error, the detail goes to the log | Standard |
| `Task_CamsgTranslate` | `CAMSG-N` turns the code into text and remaps success codes to 0 (`:143-146`) | Message dictionary: each validation message is configured once with its severity (error / warning / information) — no numeric zero convention | Configured |
| `EndEvent_ContractStored`, `EndEvent_ErrorShown` | Adapter writes the alert text into the detail panel | Transaction Console shows status; notifications go to the initiator and approvers | Standard |

### Reading the mapping as a payroll/personnel analogy

| Legacy booking element | Personnel / payroll transaction analogue (FPPS analogy, not a fact about FPPS) |
|---|---|
| Held cruise record with availability test-and-set | Position or encumbrance check made on the current record, not on a stale copy |
| Serialised contract number (MAX+1 under hold) | Unique personnel-action or pay-transaction identifier |
| `END TRANSACTION` after `STORE` | Transaction committed and visible to the next pay calculation |
| `BACKOUT TRANSACTION` on any failed edit | Transaction rejected; no partial change to the employee record |
| `CAMSG-N` codes 9902 / 9904 / 9905 / 9918 | Payroll validation edits with their message catalogue |
| `ON ERROR` backout | Job-level abend handling that leaves the master file unchanged |

## Synthetic data and scope

The model describes the public Sunny Islands Cruise sample as shipped in this repository. The FPPS column is an analogy for a Software AG Natural 9.x / ADABAS 8.6 / z/OS 2.5 estate; no FPPS source, data or production system was accessed. HCM behaviours are described as design targets for an SI to confirm against the product documentation and a configured instance.

← [`../process-flows.md`](../process-flows.md) · [`../process-to-hcm-mapping.md`](../process-to-hcm-mapping.md) · [Capability README](../README.md) · [Navigation hub](../../README.md)
