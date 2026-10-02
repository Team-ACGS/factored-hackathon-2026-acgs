# Policy corpus runbook

How to publish the policy documents and tune `search_policies`, from an applied stack to a tuned threshold.
The spec the documents follow is `SPEC.md`; the build is `uv run build-policies publish` in `data/`.

## Once

1. Apply `infra/environments/prd` and read its outputs: `policies_bucket`, `policy_documents_bucket`, `policy_index_arn`, `policies_builder_role_arn`.
2. In the Bedrock console of us-east-1, enable model access for Cohere Embed v4 (`cohere.embed-v4:0`).
3. Check that the AWS profile `personal` (the default of both commands, `--profile` to change it) is an admin of the account; the commands assume the builder role from it.
4. Copy `data/.env.example` to `data/.env` and fill `POLICIES_BUCKET`, `DOCUMENTS_BUCKET`, `POLICY_INDEX_ARN` and `POLICIES_BUILDER_ROLE_ARN` from the outputs; the other two keep their defaults.
5. Install WeasyPrint's system libraries: `sudo apt-get install libpango-1.0-0 libpangoft2-1.0-0 libharfbuzz-subset0` on Debian or Ubuntu, `brew install pango` on macOS.

## Every build

1. Upload the sources to the policies bucket at `<doc_id>/<language>.md`, or keep them in a local folder in the same layout, such as the docs root's `docs/policies/`.
   Check them first, without AWS, with `uv run build-policies validate --sources <folder>`.
2. Run `uv run build-policies publish` (sources from the bucket) or `uv run build-policies publish --sources <folder>`.
   A folder build only adds and updates: it never removes a published document missing from the folder unless you pass `--prune`; a bucket build removes the documents no longer in the bucket.
   A build that finds no source at all fails and removes nothing.
3. Fix every document the build names, with file and line, regenerating it or editing it, and run again: valid documents that did not change are skipped, so a rerun only builds what changed.
4. A changed text needs a new `version` in its frontmatter, and a changed value in `policy_facts.toml` needs a new `version` for that country; the build refuses both otherwise, so a citation in an old message keeps opening the text it cited.

The build prints the documents built, skipped and removed, the vectors written and deleted, the duplicate ratio and the chunks per document, and the corpus hash.

Never build `sample/` into prd: its documents use the real `doc_id`s, so publishing them would take the paths and versions of the real documents.
The sample exists for the tests in CI and as a worked example of the spec.

## Tuning

1. Write the labeled queries in `data/policies/queries.toml`, in the format of `sample/queries.toml`: human-written policy questions per country, each with every `answers` entry (`doc_id` and section number) that answers it, written before the first run; questions the corpus must not answer, with no `answers`; and questions in another language than the country's documents, marked with `language`.
2. Run `uv run tune-policies --queries policies/queries.toml`. It writes `data/policies/tuning.json` with the corpus hash, answer recall at 3 and at the tool's default k, overall and per document language, and one cut per language (es, pt, en): the best split that lets at most 1 in 10 of that language's unrelated questions through. Cross-language questions are reported and set no cut.
3. Commit `tuning.json`, copy its `thresholds` into `policy_min_similarity` in `infra/environments/prd/locals.tf`, and apply: the plan changes only the chatbot's `POLICY_MIN_SIMILARITY`.
4. Rerun the tuning after every build that changes the corpus hash.

## Checks after a build that changes the corpus

- `https://docs.factoredai.sdfles.com/<country>/<doc_id>-v<version>-f<facts_version>.pdf#page=N` opens a real document at page N.
- A `search_policies` call per language against the real index returns an excerpt of the expected document, and an unrelated question returns `no_match`.
