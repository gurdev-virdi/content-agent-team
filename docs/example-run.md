# Example Run

This is a sanitized example of what one successful run looks like from trigger to approval-ready draft.

## 1. Story selection

The system picks one candidate story with enough specificity and emotional clarity to work as a daily post.

Example selection summary:

```text
headline: Wildlife population rebounds after targeted habitat restoration
source: conservation news source
reason: strongest combination of specificity, emotional payoff, and clear before/after outcome
```

## 2. Caption drafting

The caption generator turns the confirmed facts into a short Instagram-ready draft.

Example excerpt:

```text
A species once pushed to the edge is returning to habitat that had gone quiet for years.

After sustained restoration work, conservation teams are now seeing visible recovery in both population numbers and breeding activity.

Save this + tag someone who needs good news today.
```

## 3. Image selection

The visual step either chooses a suitable wildlife image from an allowed provider or generates a fallback if a clean match is not available.

Expected output:

```text
image_path: output/pending/today-image.jpg
image_credit: provider or attribution string
```

## 4. Draft assembly

The local draft package combines the selected story, caption, and image reference into a single approval-ready payload.

## 5. Human approval checkpoint

Before anything is treated as final, the system sends the draft to Telegram for a manual operator decision.

Possible outcomes:

- approve and archive
- request revision and rerun parts of the workflow
- stop and inspect via Mission Control

## 6. Operator visibility

Mission Control exposes the current draft, recent run status, and manual controls so the workflow can be supervised without digging through shell output.
