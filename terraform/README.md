# Terraform Deployment for AI News Audio Briefing

This directory contains the Terraform configuration to deploy the entire application stack to Google Cloud.

## Prerequisites

1.  [Terraform CLI](https://learn.hashicorp.com/tutorials/terraform/install-cli) installed.
2.  [Google Cloud CLI](https://cloud.google.com/sdk/docs/install) installed and authenticated (`gcloud auth application-default login`).
3.  You must have a Google Cloud project with billing enabled.
4.  You must have permissions to enable APIs and create the resources defined in this configuration (e.g., `Owner` or `Editor` roles).

## How to Use

1.  **Create a `terraform.tfvars` file:**

    Create a file named `terraform.tfvars` in this directory and populate it with your specific values. This is the most secure way to provide your variables.

    ```hcl
    project_id         = "your-gcp-project-id"
    gcs_bucket_name    = "your-globally-unique-bucket-name"
    gemini_api_key     = "your-gemini-api-key"
    # region           = "europe-west1" # Optional: override default region
    # iap_allowed_emails = ["user@example.com"] # Enable IAP protection with specified users (omit or leave empty for public access)
    ```

2.  **Initialize Terraform:**

    Open your terminal in this directory and run the following command. This will download the necessary provider plugins.

    ```bash
    terraform init
    ```

3.  **Plan the Deployment:**

    Run the following command to see what resources Terraform will create. This is a dry run and will not make any changes.

    ```bash
    terraform plan
    ```

4.  **Apply the Configuration:**

    If the plan looks correct, apply the configuration to create the resources in your Google Cloud project.

    ```bash
    terraform apply
    ```

    Terraform will ask for confirmation. Type `yes` to proceed.

    The deployment will take several minutes, as it needs to build and push two container images and then provision all the cloud resources.

5.  **Access Your Application:**

    Once the `apply` command is complete, Terraform will output the URL of your web application.

    ```
    Outputs:

    webapp_url = "https://rss-summaries-webapp-xxxxxxxxxx-ew.a.run.app"
    iap_configuration = {
      "enabled" = true
      "allowed_emails" = ["user@example.com"]
      "message" = "IAP enabled"
    }
    ```

## Security Configuration

### Identity-Aware Proxy (IAP)

The application supports configurable access control through IAP (Identity-Aware Proxy):

- **Public Access (default)**: Omit `iap_allowed_emails` or set to empty list `[]` → IAP is disabled, public access enabled
- **Protected Access**: Add email addresses to `iap_allowed_emails` → IAP is enabled, public access disabled

When emails are provided in `iap_allowed_emails`:
- IAP is automatically enabled on the Cloud Run service
- Only users in `iap_allowed_emails` can access the web application  
- Users authenticate with their Google accounts
- Public access is disabled

## Cleaning Up

To destroy all the resources created by this configuration, run the following command:

```bash
terraform destroy
```
