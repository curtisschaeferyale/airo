# Register, publish and schedule a dashboard

Start here when adding a dashboard. Use one project ID consistently in its registry
entry, private installation config, CLI commands and schedule. Confirm the public
hostname, access policy, forecast conditions and any authorized paid cadence in UTC.

1. **Register the project in git.** Package the runner, instrument and static
   builder under `dashboards/NAME/`. Follow the survey runner and builder
   contracts in the [project registration guide](../packages/ops/DASHBOARDS.md#add-a-fourth-dashboard).
   Add its row to the [dashboard registry](../packages/ops/dashboard_projects.py),
   including the public data block, required files and downloads to hash.
   Include the package and its tests in the [workspace configuration](../pyproject.toml)
   and the [CI install](../.github/workflows/test.yml). Build a local preview and exercise
   the publication checks with local fixtures. Keep test forecasts out of the public site.
2. **Register the schedule in the same PR** when recurring runs have been
   requested. Add a `forecast` job with `dashboard: NAME` to the shared
   [jobs file](../packages/ops/jobs.json). Use the requested UTC cadence and
   check it against other work sharing the forecast lock. The installed site's
   private `jobs-enabled` marker controls activation. Merge through the normal
   checks and run `airo deploy --commit SHA` to install the checked bootstrap code.
3. **Install on forecast-prod.** Give the project its own private runtime JSON,
   root, results directory and socket. Point it at the shared panel runtime
   and the actual public URL. Start its origin service and confirm the existing
   minute timer dispatches `dashboardctl tick-all`. Use the
   [runtime configuration and service examples](../packages/ops/DASHBOARDS.md#install-another-site).
4. **Connect forecast-web.** Provision the hostname, TLS route, per-site document
   root, access policy and public verifier. Set the installation's `public_publisher`
   to the [shared SSH publisher](../packages/ops/DASHBOARDS.md#put-an-existing-site-on-the-shared-web-host).
   Test SSH from the forecasting service account with the same SSH config and
   target the publisher uses. HTTPS proxy settings used for GitHub and model
   APIs do not imply that SSH needs a proxy. Verify that protected HTML, release
   metadata and downloads all require the intended credentials.
5. **Publish and verify without model calls.** For a new survey with valid
   seed data or a supported empty state, run the commands below on forecast-prod.
   Replace `NAME` and `SHA` with the registered ID and full merged commit.
   For an existing dashboard, follow the guide's snapshot migration procedure
   and compare its original data and download hashes.

   ```sh
   dashboardctl NAME deploy --commit SHA --publish-data
   dashboardctl NAME smoke
   dashboardctl NAME republish
   dashboardctl NAME status
   ```

   Check the live HTTPS page and downloads, and compare its `release.json`
   frontend commit and data snapshot hash with `status`. Subsequent frontend
   deploys use `dashboardctl NAME deploy --commit SHA` to retain the published data.
6. **Enable the authorized schedule.** Create `jobs-enabled` in this installation's
   configured runtime root. Confirm `status` reports both `jobs_enabled: true`
   and the expected job ID and cadence. Check that the shared alert channel
   accepts pages for this project. A forecast failure and a publication failure
   have separate stages in the durable receipt. If only the transfer failed,
   `dashboardctl NAME republish` retries the selected snapshot without buying
   another forecast. See [schedule and recovery](../packages/ops/DASHBOARDS.md#schedule-and-recover-runs).

Report the public URL, verified release, snapshot hash and active UTC schedule
(or that scheduling is off). If a hostname, credential or network grant is
pending, identify the exact step and distinguish the staged site from the live one.
