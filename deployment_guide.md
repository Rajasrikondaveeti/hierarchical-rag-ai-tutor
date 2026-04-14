# How to Update Your Hugging Face Space Locally

This guide explains how to commit and push changes to your Hugging Face Space manually using the command line.

## Prerequisites
- **Git** installed and configured on your machine.
- **Git LFS** (Large File Storage) installed (required for PDF handling).
- A **Hugging Face Token** (access token) with `write` permissions.

## Step-by-Step Instructions

### 1. Stage Your Changes
When you modify or add files (like new lecture slides in `knowledge_base/`), you need to tell Git to track them:
```powershell
git add .
```

### 2. Commit Your Changes
Create a snapshot of your changes with a descriptive message:
```powershell
git commit -m "Brief description of what you changed"
```

### 3. Push to Hugging Face
Upload your commits to the Hugging Face repository. This will automatically trigger a build and redeploy your Space:
```powershell
git push hf main
```
> [!NOTE]
> We use the remote name `hf` because it is configured with your access token for automatic authentication.

### 4. Monitor Deployment
- Visit your Space URL: [https://huggingface.co/spaces/rajasri77/Network-Security-AI-Tutor](https://huggingface.co/spaces/rajasri77/Network-Security-AI-Tutor)
- Click on the **"Logs"** tab to see the Docker build progress.

---

## Important Tips

### Managing Large Files (PDFs)
If you add a PDF larger than 10MB, Git LFS will automatically handle it because the project is pre-configured to track `*.pdf` files with LFS.

### Handling Authentication Errors
If you are prompted for a username/password and `git push hf main` fails:
1. Ensure your token is still valid on Hugging Face.
2. You can re-run:
   ```powershell
   git remote set-url hf https://<your_username>:<your_token>@huggingface.co/spaces/rajasri77/Network-Security-AI-Tutor
   ```

### Working with .gitignore
If you add a file to `.gitignore`, it will NOT be pushed. For this AI Tutor, **do not** ignore the `knowledge_base/` PDFs, as the app needs them to build its internal database.
