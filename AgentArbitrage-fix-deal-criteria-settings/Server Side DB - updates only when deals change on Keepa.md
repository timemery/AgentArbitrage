# Discussion with Jules on building a Persistent, Near Real-Time Deals Database. 

Help composing a task description ONLY. Not to actually implement it, only to research the best possible way to accomplish this goal in the best way possible so that I can open that as a new task:

Can you help me understand the scope and feasability to create a server side database of all deals?

The goal would be that instead of doing a scan of the Keepa API on demand every time we want a fresh set of data, we implement some kind of listener (or something smarter) function that will listen to the API for changes, and update only the deals that change as soon as they change by looking at the "last price change" column, and also when a deal that's already in the db and listed by a certain seller with the lowest price that we display in the "Now" column in the web UI changes to a lower price by the same seller, or a lower price by any seller, then that one row updates without user interaction.

The same would have to happen when a NEW deal is added to the Keepa Deals page (the one based on my Keepa user parameters that we use somewhere in the code - not sure where now) that deal gets called into our db, and added to the web UI without user intervention, and without running a data scan. We would also need to "listen" for any new deals that are added, then add those to our DB and update the web UI with that new deal. and of course when a deal no longer qualifies as a deal (acording to the keepa API) then that deal drops out of the db, and is removed from the web UI.

The benefit would be that we would never have to run a scan and wait for it to finish, and instead the list of deals on the dashboard would always have current deals that reflect the same deals and those deals current prices as they appear on Keepa deals site itself.

I'd like to know if this job is so big it will have to be broken down into smaller tasks or if its easier than it sounds and can be implemented without a whole lot of upheaval.

Whether its easy or needs to be broken into a series of smaller tasks, can you please help me by proposing a way to make this work, and then composing a task description in order to implement this addition in a later task?



------

### **Task Description for Future Implementation**

**Project: Implement a Persistent, Near Real-Time Deals Database**

**Objective:** Convert the application's data pipeline from a manual, on-demand batch process to an automated, near real-time system. The goal is to maintain a persistent server-side database (`deals.db`) that continuously and incrementally updates with the latest deals from the Keepa API without requiring a user-initiated full scan.

------

#### **Part 1: The "Upserter" - Incremental Deal Updating**

This is the core of the new system. It involves creating a new process to fetch and apply recent changes.

**1. Create a New Database Schema for Incremental Updates:**

- Modify the `deals` table in `deals.db`.
- Add a new column: `last_seen_utc TIMESTAMP`. This will be updated every time a deal is seen in a poll.
- Ensure the `ASIN` column is indexed for fast lookups to avoid duplicates.

**2. Develop the "Upserter" Celery Task:**

- Create a new Celery task, let's call it `update_recent_deals`. This task will be the heart of the new system.

- This task should run on a recurring schedule (e.g., every 15 minutes).

- API Call:

   

  The task will call the Keepa

   

  ```
  /deal
  ```

   

  endpoint. The query should be optimized to only fetch recently changed items. Key parameters to use are:

  - `dateRange: 0` (fetches deals from the last 24 hours).
  - `deltaLastRange`: To capture recent price drops.
  - The existing filters from the user's settings should be applied to ensure the deals are relevant.

**3. Implement "Upsert" Logic:**

- For each deal returned by the API:
  - **Check Existence:** Query the local `deals.db` to see if a record with the same `ASIN` already exists.
  - **Update:** If the ASIN exists, update the existing row with the new data (price, rank, etc.) and update the `last_seen_utc` timestamp to the current time.
  - **Insert:** If the ASIN does not exist, fetch its full product details (similar to the existing `run_keepa_script` logic) and insert a new row into the database, setting the `last_seen_utc` timestamp.
- **Important:** This process must **not** drop or wipe the table. It should only perform `INSERT` and `UPDATE` operations.

------

#### **Part 2: The "Pruner" - Database Cleanup**

This process ensures the database doesn't fill up with deals that are no longer active.

**1. Develop the "Pruner" Celery Task:**

- Create a second new Celery task, let's call it `prune_stale_deals`.
- This task should run on a less frequent schedule (e.g., once every 12 or 24 hours).

**2. Implement Pruning Logic:**

- The task will query the `deals.db` for records where the `last_seen_utc` timestamp is older than a specified threshold (e.g., more than 48 hours ago).
- Any records matching this criterion are considered "stale" (i.e., they haven't appeared in the recent deals feed) and should be deleted from the database.

------

#### **Part 3: System Integration**

This involves removing the old system and integrating the new one.

**1. Modify the Web UI:**

- Remove the "Run Scan" button and the scan status indicator from the dashboard. The data will now update automatically in the background.
- The dashboard will now always show the data directly from the `deals.db`, which will be continuously updated.

**2. Decommission the Old Batch Script:**

- The existing `run_keepa_script` Celery task and its associated logic for full, destructive scans will no longer be needed for the main user-facing functionality and can be removed or disabled.

**3. Configuration and Management:**

- Add configuration settings for the schedules of the `update_recent_deals` and `prune_stale_deals` tasks.
- Ensure the new Celery tasks are correctly registered and scheduled by the Celery Beat scheduler.

Today 18:23

That sounds awesome. So you're proposing these three parts to be done one at a time, a single part per task. I like that idea since it sounds like a big enough task that trying to do all three on one task would overload your system. One question... Can this last part include a "Refresh deals" link on the dashboard that users can trigger a refresh? Or would that be a bad idea. The other question is, what happens when we add/remove change/improve any of the columns we're already showing in the web ui, as well as potentially new ones... to date, in order to test those new or updated features, we've had to run a new scan to see the results. Will this have to be done to see updates, or additions to the dashboard?

Those are excellent and very important questions. They get to the heart of how this new system would operate in practice. Let me address them both.

**1. Can we have a "Refresh deals" link on the dashboard?**

Yes, absolutely. That's a great idea. While the automated background tasks would keep the data fresh, adding a manual "Refresh Deals" link is straightforward and gives you immediate control.

- **How it would work:** The link would trigger the "Upserter" task (`update_recent_deals`) to run immediately, outside of its normal schedule. The dashboard could show a small spinner, and once the task is complete, the new data would appear automatically. This is very similar to how the "Recalculate" button works on the settings page, so it's a familiar and proven pattern in this application.

**2. What happens when we add or change columns?**

This is a critical point, and you're right to ask. The current workflow of "run a full scan to see changes" would be replaced by a more robust, two-step process for handling schema changes:

- **Step 1: The "Upserter" is updated.** First, the code for the `update_recent_deals` task would be modified to calculate and populate the new column for any new or updated deals it processes. This ensures all deals going forward are complete.
- **Step 2: A One-Time "Backfill" is run.** For all the deals *already in the database*, we would need to populate the new column. We can create a dedicated, manually-triggered task for this—let's call it `backfill_all_deals`. After deploying a code change with a new column, you would run this backfill task once. It would iterate through every deal in the database, fetch the necessary information, and fill in the data for the new column.

This "backfill" process is the new equivalent of running a full scan to see your changes. It's more efficient because it only targets the missing information without disrupting the entire database.

So, the new workflow for adding a column would be:

1. Add the new logic to the code.
2. Run a one-time backfill task to update existing records.
3. Let the automated "Upserter" handle new deals from then on.

This approach gives us the best of both worlds: a self-updating, real-time database for daily use and a clear process for handling structural changes and testing new features.

Today 18:55

Ok, this all sounds awesome. One more concern.... Currently the parameters I have set limit the total deals to somewhere between 700 and 1000+ ASINs, but I want to expand that to include nearly all ASINs that qualify as a Deal (according to Keepa) which would bump that number up to 3000 to potentially more than 5000 ASINs. What impact will this have on what you're proposing?

That's the perfect question to ask, as it directly addresses the scalability of the new system. I'm happy to say that the proposed architecture is not only capable of handling this increase, but it's specifically designed to make scaling from 1,000 to 5,000+ deals efficient and cost-effective.

Here’s a breakdown of the impact of that larger deal volume:

**1. API Token Cost & Efficiency:** This is where the new model truly shines. With the current "full scan" method, increasing the scope to 5,000 deals would mean that every single scan would be 5x more expensive and 5x slower.

With the new "Upserter" model:

- **Cost is Tied to Change, Not Size:** The system primarily polls for *what has changed recently*. The ongoing token cost is determined by the number of deals that had a price drop in the last 15 minutes, not the 5,000+ deals sitting in the database.
- **Initial "Fill-up" Cost:** When you first broaden your criteria, there will be a one-time "fill-up" period where the "Upserter" task discovers thousands of new deals. It will work through them over a few cycles, fetching the full data for each. This will cause a temporary spike in token usage.
- **Stable, Lower-Cost Operation:** After the initial fill-up, the system will return to its low-cost, steady state of only processing recent updates. This is vastly more efficient than repeatedly running a full 5,000-deal scan.

**2. Database Performance:** A database of 5,000 or even 50,000 rows is still very manageable for SQLite, *as long as it's designed correctly*. The key is **indexing**.

- My proposal includes adding a database index to the `ASIN` column. This acts like an index in a book, allowing the database to find any deal almost instantly, whether the table has 1,000 or 100,000 rows. Without this, queries would slow down as the table grows, but with it, performance remains lightning-fast. The same would apply to the `last_seen_utc` column to make the "Pruner" task efficient.

**3. Worker Processing Time:**

- The background tasks (`update_recent_deals`, `prune_stale_deals`) will naturally take longer to run with more data. However, since they are asynchronous background jobs, **you will not feel this delay**. A task taking 3 minutes to run instead of 1 minute has no impact on your experience using the dashboard. The system is designed for this kind of background work.

**In short, your desire to expand the number of deals is the exact reason to move to this new architecture.** The current full-scan model would become increasingly slow and expensive as you scale up. The proposed "Upserter/Pruner" model is built to handle that growth gracefully, efficiently, and cost-effectively.

Awesome! Do any of my questions or concerns change the original task description you've provided above? If so can you provide a new "final" task description for me?

Excellent question. Your feedback has definitely helped refine the plan and make it more robust. The core of the task remains the same, but I've updated the description to explicitly include the "Refresh" button and the process for handling future column changes (the "backfill" task). This makes the plan more complete and actionable.

Here is the final, updated task description.

------

### **Final Task Description: Implement a Persistent, Near Real-Time Deals Database**

**Objective:** Convert the application's data pipeline from a manual, on-demand batch process to an automated, near real-time system. The goal is to maintain a persistent server-side database (`deals.db`) that continuously and incrementally updates with the latest deals from the Keepa API without requiring a user-initiated full scan, while providing tools for manual control and future maintenance.

------

#### **Part 1: The "Upserter" - Incremental Deal Updating**

This is the core of the new system. It involves creating a new process to fetch and apply recent changes.

1. **Modify the Database Schema:**
   - In `deals.db`, add a new column: `last_seen_utc TIMESTAMP`. This will be updated every time a deal is seen in a poll.
   - Ensure the `ASIN` column is indexed for fast lookups to avoid duplicates and ensure high performance.
2. **Develop the "Upserter" Celery Task:**
   - Create a new Celery task named `update_recent_deals`. This task will be the heart of the new system.
   - It should run on a recurring schedule (e.g., every 15 minutes) managed by Celery Beat.
   - **API Call:** The task will call the Keepa `/deal` endpoint, optimized to fetch only recently changed items (e.g., using `dateRange: 0` and other relevant filters). It should apply the user's deal criteria from `settings.json`.
3. **Implement "Upsert" Logic:**
   - For each deal returned by the API:
     - **Check Existence:** Query the local `deals.db` to see if a record with the same `ASIN` already exists.
     - **Update:** If it exists, update the existing row with the new data (price, rank, etc.) and update the `last_seen_utc` timestamp to the current time.
     - **Insert:** If it does not exist, fetch its full product details (reusing logic from the old `run_keepa_script`) and insert a new row into the database, setting the `last_seen_utc` timestamp.
   - **Crucially, this process must not drop or wipe the table.** It should only perform atomic `INSERT` and `UPDATE` operations.

------

#### **Part 2: The "Pruner" - Database Cleanup**

This process ensures the database doesn't fill up with deals that are no longer active.

1. **Develop the "Pruner" Celery Task:**
   - Create a second new Celery task named `prune_stale_deals`.
   - This task should run on a less frequent schedule (e.g., once every 24 hours).
2. **Implement Pruning Logic:**
   - The task will query the `deals.db` for records where the `last_seen_utc` timestamp is older than a specified threshold (e.g., more than 48 hours ago).
   - Records matching this criterion are considered "stale" and should be deleted from the database.

------

#### **Part 3: System and UI Integration**

This involves removing the old system and exposing the new functionality to the user.

1. **Modify the Web UI:**
   - **Remove** the "Run Scan" button and the entire scan status indicator from the dashboard.
   - **Add** a new "Refresh Deals" link or button. This button will trigger the `update_recent_deals` task to run immediately, providing on-demand freshness.
2. **Decommission the Old Batch Script:**
   - The existing `run_keepa_script` Celery task and its associated logic should be disabled or removed, as its functionality is now replaced by the "Upserter" and "Pruner" tasks.
3. **Configuration:**
   - Add configuration settings for the schedules of the `update_recent_deals` and `prune_stale_deals` tasks.

------

#### **Part 4: Maintenance & Future Development Workflow**

This part ensures the new system is maintainable and extensible.

1. Create a "Backfill" Task for Schema Migrations:
   - Develop a new, manually-triggered Celery task named `backfill_all_deals`.
   - **Purpose:** When a new column is added to the application, this task will be run once to populate that column for all existing records in the database.
   - **Logic:** It will iterate through every record in the `deals` table, calculate or fetch the required data for the new column(s), and `UPDATE` the row. This replaces the need to run a full, destructive scan to see new features.

One tiny tweak I forgot to ask about. It would be informative, to users to know how many deals are currently available to search. Can we add that feature to the task description as well?

Of course. That's an excellent idea for providing context to the user. I've integrated that request into the final task description under the UI section.

Here is the final version, which now includes the deal count display. This should cover everything we've discussed.

------





Here is the final version, which now includes the deal count display. This should cover everything we've discussed.

------



### **Implement a Persistent, Near Real-Time Deals Database**

Part 1 of 4 
Note: for background on all 4 steps please read the brainstorming document found in the root of the repo: Server Side DB - updates only when deals change on Keepa.md

**Objective:** Convert the application's data pipeline from a manual, on-demand batch process to an automated, near real-time system. The goal is to maintain a persistent server-side database (`deals.db`) that continuously and incrementally updates with the latest deals from the Keepa API without requiring a user-initiated full scan, while providing tools for manual control and future maintenance.

------

#### **Part 1: The "Upserter" - Incremental Deal Updating**

This is the core of the new system. It involves creating a new process to fetch and apply recent changes.

1. **Modify the Database Schema:**
   - In `deals.db`, add a new column: `last_seen_utc TIMESTAMP`. This will be updated every time a deal is seen in a poll.
   - Ensure the `ASIN` column is indexed for fast lookups to avoid duplicates and ensure high performance.
2. **Develop the "Upserter" Celery Task:**
   - Create a new Celery task named `update_recent_deals`. This task will be the heart of the new system.
   - It should run on a recurring schedule (e.g., every 15 minutes) managed by Celery Beat.
   - **API Call:** The task will call the Keepa `/deal` endpoint, optimized to fetch only recently changed items (e.g., using `dateRange: 0` and other relevant filters). It should apply the user's deal criteria from `settings.json`.
3. **Implement "Upsert" Logic:**
   - For each deal returned by the API:
     - **Check Existence:** Query the local `deals.db` to see if a record with the same `ASIN` already exists.
     - **Update:** If it exists, update the existing row with the new data (price, rank, etc.) and update the `last_seen_utc` timestamp to the current time.
     - **Insert:** If it does not exist, fetch its full product details (reusing logic from the old `run_keepa_script`) and insert a new row into the database, setting the `last_seen_utc` timestamp.
   - **Crucially, this process must not drop or wipe the table.** It should only perform atomic `INSERT` and `UPDATE` operations.

------

#### **Part 2: The "Pruner" - Database Cleanup**

This process ensures the database doesn't fill up with deals that are no longer active.

1. **Develop the "Pruner" Celery Task:**
   - Create a second new Celery task named `prune_stale_deals`.
   - This task should run on a less frequent schedule (e.g., once every 24 hours).
2. **Implement Pruning Logic:**
   - The task will query the `deals.db` for records where the `last_seen_utc` timestamp is older than a specified threshold (e.g., more than 48 hours ago).
   - Records matching this criterion are considered "stale" and should be deleted from the database.

------

#### **Part 3: System and UI Integration**

This involves removing the old system and exposing the new functionality to the user.

1. **Modify the Web UI:**
   - **Remove** the "Run Scan" button and the entire scan status indicator from the dashboard.
   - **Add** a new "Refresh Deals" link or button. This button will trigger the `update_recent_deals` task to run immediately, providing on-demand freshness.
   - **Display Total Deal Count:** Create a new, simple API endpoint (e.g., `/api/total_deals`) that returns the current number of rows in the `deals.db` table. On the dashboard, add a display element that calls this endpoint to show the user the total number of deals available in the database.
2. **Decommission the Old Batch Script:**
   - The existing `run_keepa_script` Celery task and its associated logic should be disabled or removed, as its functionality is now replaced by the "Upserter" and "Pruner" tasks.
3. **Configuration:**
   - Add configuration settings for the schedules of the `update_recent_deals` and `prune_stale_deals` tasks.

------

#### **Part 4: Maintenance & Future Development Workflow**

This part ensures the new system is maintainable and extensible.

1. Create a "Backfill" Task for Schema Migrations:
   - Develop a new, manually-triggered Celery task named `backfill_all_deals`.
   - **Purpose:** When a new column is added to the application, this task will be run once to populate that column for all existing records in the database.
   - **Logic:** It will iterate through every record in the `deals` table, calculate or fetch the required data for the new column(s), and `UPDATE` the row. This replaces the need to run a full, destructive scan to see new features.