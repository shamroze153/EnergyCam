/**
 * HFM alert email cleanup (for the RECEIVER's Gmail account)
 * -----------------------------------------------------------
 * Permanently deletes HFM alert emails (which carry blurred snapshots)
 * older than 1 day. Runs once a day by itself.
 *
 * Only deletes an email when BOTH are true:
 *   1. it was sent FROM the alert sender address (HFM_SENDER below), and
 *   2. its subject starts with "HFM" or "[AFTER-HOURS] HFM".
 * So normal work emails that happen to mention HFM are never touched.
 *
 * SETUP (one time, ~5 minutes, logged in as the receiver):
 *   1. Open https://script.google.com -> "New project".
 *   2. Delete the sample code, paste this whole file, and set HFM_SENDER
 *      below to the alert sender's email address (SENDER_EMAIL in .env).
 *   3. Left menu: "Services" (+) -> choose "Gmail API" -> Add.
 *      (Needed for PERMANENT delete; without it emails only go to Trash.)
 *   4. Top menu: choose function "dryRun" -> Run. Approve the permissions
 *      Google asks for. Check "Execution log": it lists what WOULD be
 *      deleted, without deleting anything.
 *   5. If the list looks right, choose "installDailyTrigger" -> Run (once).
 *      Done. Check "Triggers" (clock icon) to see the daily job.
 *
 * To stop it: Triggers (clock icon) -> delete the trigger.
 */

const HFM_SENDER = 'PUT_ALERT_SENDER_EMAIL_HERE';
const MAX_AGE = '1d';

function findHfmMessages_() {
  if (HFM_SENDER.indexOf('@') === -1) {
    throw new Error('Set HFM_SENDER to the alert sender email address first.');
  }
  const query = 'from:' + HFM_SENDER + ' subject:HFM older_than:' + MAX_AGE + ' in:anywhere';
  const found = [];
  let start = 0;
  while (true) {
    const threads = GmailApp.search(query, start, 100);
    if (threads.length === 0) break;
    threads.forEach(function (thread) {
      thread.getMessages().forEach(function (msg) {
        const subject = msg.getSubject() || '';
        const fromOk = msg.getFrom().toLowerCase().indexOf(HFM_SENDER.toLowerCase()) !== -1;
        const subjectOk = subject.indexOf('HFM') === 0 || subject.indexOf('[AFTER-HOURS] HFM') === 0;
        if (fromOk && subjectOk) found.push(msg);
      });
    });
    start += threads.length;
  }
  return found;
}

/** Lists what would be deleted. Deletes nothing. */
function dryRun() {
  const msgs = findHfmMessages_();
  msgs.forEach(function (m) { Logger.log(m.getDate() + '  |  ' + m.getSubject()); });
  Logger.log('Dry run: ' + msgs.length + ' email(s) would be permanently deleted.');
}

/** Permanently deletes matching emails. Called daily by the trigger. */
function cleanupHfmEmails() {
  const msgs = findHfmMessages_();
  let deleted = 0;
  msgs.forEach(function (m) {
    try {
      Gmail.Users.Messages.remove('me', m.getId()); // permanent (skips Trash)
      deleted++;
    } catch (e) {
      Logger.log('Could not delete one message: ' + e);
    }
  });
  Logger.log('HFM cleanup: ' + deleted + ' email(s) permanently deleted.');
}

/** Run once to schedule cleanupHfmEmails every day (~2 AM). */
function installDailyTrigger() {
  ScriptApp.getProjectTriggers().forEach(function (t) {
    if (t.getHandlerFunction() === 'cleanupHfmEmails') ScriptApp.deleteTrigger(t);
  });
  ScriptApp.newTrigger('cleanupHfmEmails').timeBased().everyDays(1).atHour(2).create();
  Logger.log('Daily cleanup trigger installed.');
}
