# Deployment Checklist

## 1. Pre-Commit Check
- [ ] Did I remove any hardcoded API keys or passwords?
- [ ] Did I test the changes locally (`flask run`)?
- [ ] Did I check the logs for errors?

## 2. The Git Workflow
1. `git status` (See what changed)
2. `git add .` (Stage all changes)
3. `git commit -m "Descriptive message"` (Save changes)
4. `git push` (Send to GitHub/Render)

## 3. Post-Deploy Verification
- [ ] Go to `https://predictability-api.com`
- [ ] Check the Console (F12) for red errors.
- [ ] Test the Calculator (Run a calculation).
- [ ] Check the Demos (`/demo/industrial`, `/demo/sports`).
- [ ] Check Render Logs for "Build Successful".

## 4. Marketing (Optional)
- [ ] Post update on Twitter/X?
- [ ] Update Changelog in API Docs?
