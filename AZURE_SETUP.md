# Azure Hosting Setup Guide (Azure Container Apps)

This guide explains how to host your MAS ChatBot on **Azure Container Apps** with automatic deployment from GitHub.

## 1. Important: Use Azure Cloud Shell
You don't need to install anything on your computer. 
1. Log in to the [Azure Portal](https://portal.azure.com).
2. Click the **Cloud Shell** icon (`>_`) at the top right of the screen (next to the search bar).
3. If asked, choose **Bash**.

## 2. Finding your IDs
- **Subscription ID**: 
  - In the portal search bar, type **Subscriptions**.
  - Click your subscription. The ID is a long string (e.g., `48a2ab83-e9ec-4ff5-...`).
- **Resource Group**: 
  - In the portal search bar, type **Resource groups**.
  - Use the name of the group where you created your Container App (e.g., `mas-chatbot-rg`).

## 3. Create the Credentials (Fixes Authorization Errors)
Run this command in the **Azure Cloud Shell** (NOT your local terminal). This gives GitHub permission to manage your app.

```bash
az ad sp create-for-rbac --name "maschatbot-github-deploy" --role contributor --scopes /subscriptions/<SUBSCRIPTION_ID>/resourceGroups/<RESOURCE_GROUP_NAME> --sdk-auth
```
- Replace `<SUBSCRIPTION_ID>` with your ID.
- Replace `<RESOURCE_GROUP_NAME>` with your group name (e.g., `mas-chatbot-rg`).

**Copy the entire JSON output** (including the `{` and `}`) and paste it into the `AZURE_CREDENTIALS` secret in GitHub.

## 4. GitHub Secrets Checklist
Ensure these are exactly right in **GitHub Repository** -> **Settings** -> **Secrets** -> **Actions**:

| Secret Name | Example Value |
| :--- | :--- |
| `AZURE_CREDENTIALS` | `{ "clientId": "...", ... }` (The full JSON) |
| `AZURE_RESOURCE_GROUP` | `mas-chatbot-rg` |
| `AZURE_CONTAINER_REGISTRY_NAME` | `maschatbot` (just the name) |
| `AZURE_CONTAINER_REGISTRY_URL` | `maschatbot.azurecr.io` |
| `AZURE_CONTAINER_REGISTRY_USERNAME` | `maschatbot` |
| `AZURE_CONTAINER_REGISTRY_PASSWORD` | `(your_acr_password)` |

## 5. Troubleshooting "AuthorizationFailed"
If you still see "does not have authorization", it means the Service Principal was created for the wrong "Scope". 
- Delete the old secret in GitHub.
- Run the command in Step 3 again, making triple-sure the `SUBSCRIPTION_ID` and `RESOURCE_GROUP_NAME` match exactly what is in your portal.
