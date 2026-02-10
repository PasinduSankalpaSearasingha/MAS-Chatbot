# Azure Hosting Setup Guide

This guide explains how to set up the MAS ChatBot on Azure App Service as a containerized app with GitHub Actions.

## 1. Azure Resources Required

1.  **Azure Container Registry (ACR)**: To store your Docker images.
    - Create an ACR in the Azure Portal.
    - Enable "Admin user" in the ACR Access Keys settings.
2.  **Azure App Service**: To host the application.
    - Create a "Web App for Containers".
    - Choose "Linux" as the OS.
    - Under "Docker", you can initially set a placeholder image or leave it for the CI/CD to handle.

## 2. GitHub Secrets

Go to your GitHub Repository -> Settings -> Secrets and variables -> Actions and add the following secrets:

| Secret Name | Description |
| :--- | :--- |
| `AZURE_CONTAINER_REGISTRY_URL` | The login server of your ACR (e.g., `myregistry.azurecr.io`). |
| `AZURE_CONTAINER_REGISTRY_USERNAME` | The admin username for your ACR. |
| `AZURE_CONTAINER_REGISTRY_PASSWORD` | The admin password for your ACR. |
| `AZURE_WEBAPP_PUBLISH_PROFILE` | The Publish Profile content from your Azure Web App (Download from Azure Portal). |

## 3. Environment Variables (Azure)

In the Azure Portal, go to your App Service -> Configuration -> Application settings and add your `.env` variables there:

- `OPENAI_API_KEY`
- `ASTRA_DB_APPLICATION_TOKEN`
- `ASTRA_DB_API_ENDPOINT`
- ... (any other keys from your current `.env` file)
- **CRITICAL**: Add `WEBSITES_PORT` and set it to `8000`.

## 4. Deployment

Once the secrets are set, push your changes to the `main` branch. The GitHub Action will automatically:
1. Build the Docker image.
2. Push it to ACR.
3. Deploy it to the App Service.
