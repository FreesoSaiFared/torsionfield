# An Agent Is Not Its Computer

*What invisible_dots gets right about persistent AI — and why a virtual machine should be a possible home, not the definition of an agent.*

An AI agent opens a browser, signs in, retrieves an invoice, writes a note, and shuts down. Tomorrow it starts again. The remarkable part is not that it can use a computer. The remarkable part is that tomorrow's work can belong to the same continuing undertaking. What, exactly, must persist for that to be true?

[invisible_dots](https://github.com/feder-cr/invisible_dots), developed by feder-cr, answers with unusual concreteness: give each Dot its own hardware-accelerated QEMU virtual machine, persistent disk, browser identities, notes, skills, approvals, and scheduled work. The machine sleeps when idle and wakes to continue. There is a real control plane, durable task delivery, and an explicit account of what happens when an operation is interrupted.

This is more interesting than another demonstration of an agent clicking buttons. It is an attempt to make autonomous work survive contact with the ordinary instability of computers.

It also puts an architectural question in unusually sharp relief: **must the agent and its computer share a lifetime?**

## The engineering deserves credit

The project's most compelling feature is not the patched Firefox browser. It is its treatment of interrupted work. The host persists accepted messages and tasks; the guest records its reasoning steps and their corresponding events transactionally. An in-flight tool call whose result was never recorded is not automatically retried. It becomes an explicitly uncertain outcome that the agent must investigate.

That distinction is fundamental. A system that silently repeats a payment, a deletion, or a publication after a crash is not reliable merely because its queue survived. invisible_dots does not confuse an unfinished invocation with permission to invoke it again.

There are other thoughtful choices. Golden VM images are separated from the runtime code supplied on a read-only disk. Approvals can wait across restarts. Browser profiles keep session state. Resource limits and permission categories are visible rather than being hidden in an optimistic system prompt. The [architecture document](https://github.com/feder-cr/invisible_dots/blob/main/docs/architecture.md) is unusually explicit about mechanisms, failure cases, and constraints.

A criticism worth publishing must begin there. A persistent VM is a defensible unit of *isolation*. In some circumstances it is precisely the right one.

## Persistence is not yet continuity

A Dot has a durable identifier and host-side configuration, so it would be inaccurate to say that the project literally identifies an agent with a QEMU process. But the working continuity of its conversation, memory, skills, and browser identities is housed inside that particular guest filesystem. In the current release there is no multi-host orchestration, no snapshot-and-restore facility, and no supported migration to a newer golden image.

This is not evidence of poor engineering. It is a deliberate product boundary. It is also the point at which we would choose another primitive.

An agent has several kinds of continuity. It can remember what was said. It can retain the authority it was granted, or recognize when that authority has expired. It can resume an undertaking whose previous steps were performed elsewhere. Most importantly, it can distinguish what it *attempted* from what actually became true.

None of those continuities logically requires the same machine, disk, browser engine, model provider, or active conversation window. A machine can preserve them conveniently, but convenience should not quietly become identity.

Our proposed alternative is a durable actor and operation history whose execution environment is replaceable. A VM could be provisioned for a risky task, a browser attached for a web interaction, a remote host selected for a workload, and a different reasoning model used for review. The identity of the undertaking would remain stable across those changes. That is a research direction, not a capability we claim to have fully demonstrated.

## A recorded action is not a verified effect

invisible_dots correctly marks interrupted tool calls as uncertain. We would extend that principle beyond crash recovery into the definition of success.

Suppose an agent clicks “Submit” and its browser crashes before receiving confirmation. The event log can show that the click was attempted. The site's server may have processed it, rejected it, or processed it twice through behavior outside the agent's control. At-most-once *tool invocation* is not exactly-once *real-world effect*.

A useful execution record therefore needs more than a tool name, arguments, and completion status. It needs an intended postcondition, the observations that bear on it, the authority under which the action was attempted, and a procedure for resolving ambiguity without carelessly repeating the action.

This is the distinction behind Torsionfield's formulation: **intelligence must leave evidence**. The machine's account is evidence of what the machine did. It is not automatically evidence of what happened in the world.

## The browser profile is an excellent container, not an identity theory

invisible_dots uses separate persistent Firefox profiles, backed by a modified browser engine intended to reduce automation fingerprints. That is practical. It keeps cookies and logins available to a Dot across restarts, and its guide sensibly stops short of promising that a website cannot detect or refuse automation.

But a profile is a bundle of executable state, credentials, storage, browser-specific assumptions, and contingent permissions. Copying it elsewhere is not the same as transferring legitimate authority. Nor should portability require leaking session secrets to every execution environment.

The more difficult design is a browser identity that can be *referenced*, *delegated*, *revoked*, and *reconstituted* through explicitly authorized mechanisms, while sensitive credentials remain inside appropriate trust boundaries. A browser session can then be an attachment to an agent rather than the agent's permanent residence.

This matters particularly for work spanning browser automation, desktop tools, command-line programs, hosted services, and MCP capabilities. The current Dot deliberately offers general file and shell tools but exposes only its own browser through MCP. That gives it a coherent, inspectable boundary; it also limits what can become a shared capability in a wider execution network.

## Skills are not yet learned procedures

The Dot can write notes and skill files describing how it performs recurring work. This is useful memory. It is not the same thing as learning a reliable procedure from the execution itself.

Imagine watching a successful interaction unfold: the selectors tried, the dialogs dismissed, the page states observed, the requests made, the permissions exercised, and the final effect independently checked. The valuable object is not merely a prose summary that says how to repeat the task. It is an evidence-backed trace that can be generalized, challenged, and selectively turned into reusable operations.

We want such traces to become capabilities: sometimes deterministic browser steps, sometimes a prompt with explicit constraints, sometimes a script, sometimes an MCP tool, and sometimes a deliberately unresolved experimental branch. A procedure should improve when its assumptions fail, without rewriting the history that showed those assumptions failing.

That is a larger ambition than persistent skill files, not an argument against them. They may be one of the best human-readable projections of a more substantial record.

## What would change our minds?

The fair response to an architectural thesis is an experiment, not a diagram. We would first reproduce the project's documented recovery scenario on a real accelerated VM: accept a task, interrupt it between a consequential action and its result, recover it, and compare the agent's account with the external system's actual state. The published guide reports a fifteen-step Linux/KVM acceptance run, but we have **not** independently reproduced it.

Next, we would test a different question: can the *same undertaking* continue when its computer, browser implementation, or model changes, without copying a privileged entire guest filesystem? That capability is explicitly outside the present invisible_dots scope; the experiment would compare it with an alternative design rather than count its absence as a failed promise.

Finally, we would ask whether a workflow learned once can be recovered from its evidence, adapted to a changed interface, executed with narrower delegated authority, and independently checked. Not “did the model say it succeeded?”, but “can another observer establish the result?”

These tests have different success criteria. A persistent private computer may win on isolation and simplicity. A portable capability system may win on reconstruction, interoperability, and shared learning. The answer could be hybrid.

## The transductive alternative

The conventional picture of a personal agent is a small digital worker sitting inside a small digital office. Give it a desk, a browser, files, and an identity; make the office persistent; and the worker can resume tomorrow.

Our proposition is more radical: **agency should reside in the continuity of accountable action, not in the persistence of a particular workspace.**

A website interaction can become a reusable method. A failed method can become an explicit counterexample. A completed operation can change a shared knowledge structure only to the extent that its effects were observed. A capability can move between execution environments while its authorization remains bounded and revocable. The user should not have to supervise the machinery that makes this possible; the user should retain control over purposes, permissions, and consequential decisions.

That does not abolish virtual machines. It gives them a more precise role. A Dot-like VM could become a temporary, isolated execution habitat within a larger fabric of identities, capabilities, histories, and evidence. Some agents might live there for months. Others might inhabit it for a single transaction. Neither choice should determine whether the underlying work can continue.

invisible_dots has built an impressively concrete answer to the question, “How do we give an agent a computer that remembers?” The question we want to pursue is different: **“How do we give an undertaking continuity even when every computer involved is replaceable?”**

A Dot is an interesting container for persistence. The next architectural step is to make continuity independent of the container.

---

**Evidence and status — 10 October 2026.** This is a source-based critical interpretation, not an independent security audit, performance benchmark, or real-VM acceptance report. Product descriptions and stated limitations are drawn from the [invisible_dots guide](https://github.com/feder-cr/invisible_dots/blob/main/docs/guide.md), [architecture contract](https://github.com/feder-cr/invisible_dots/blob/main/docs/architecture.md), and [repository](https://github.com/feder-cr/invisible_dots). The proposed alternative and experiments are Torsionfield research hypotheses. No test results for them are claimed here.
