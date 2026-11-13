terraform {
  required_version = ">= 1.6"
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 4.10"
    }
  }
}

provider "azurerm" {
  features {}
  subscription_id = var.subscription_id
}

variable "subscription_id" {
  type = string
}

variable "location" {
  type    = string
  default = "germanywestcentral"
}

variable "openai_location" {
  description = "Region with the model deployments; Sweden Central keeps processing in the EU"
  type        = string
  default     = "swedencentral"
}

variable "name" {
  type    = string
  default = "utility-agent"
}

variable "image" {
  description = "Container image, e.g. myregistry.azurecr.io/utility-agent:<git sha>"
  type        = string
}

variable "alert_email" {
  type = string
}

variable "model_deployments" {
  description = "Deployment name => model name and version; the release config refers to deployment names"
  type = map(object({
    model    = string
    version  = string
    capacity = number
  }))
}

locals {
  tags = { service = var.name, managed_by = "terraform" }
}

data "azurerm_client_config" "current" {}

resource "azurerm_resource_group" "main" {
  name     = "rg-${var.name}"
  location = var.location
  tags     = local.tags
}

resource "azurerm_log_analytics_workspace" "main" {
  name                = "log-${var.name}"
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  sku                 = "PerGB2018"
  retention_in_days   = 30
  tags                = local.tags
}

resource "azurerm_application_insights" "main" {
  name                = "appi-${var.name}"
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  workspace_id        = azurerm_log_analytics_workspace.main.id
  application_type    = "web"
  tags                = local.tags
}

resource "azurerm_user_assigned_identity" "app" {
  name                = "id-${var.name}"
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  tags                = local.tags
}

resource "azurerm_key_vault" "main" {
  name                       = "kv-${var.name}"
  location                   = azurerm_resource_group.main.location
  resource_group_name        = azurerm_resource_group.main.name
  tenant_id                  = data.azurerm_client_config.current.tenant_id
  sku_name                   = "standard"
  enable_rbac_authorization  = true
  purge_protection_enabled   = true
  soft_delete_retention_days = 30
  tags                       = local.tags
}

resource "azurerm_role_assignment" "app_reads_secrets" {
  scope                = azurerm_key_vault.main.id
  role_definition_name = "Key Vault Secrets User"
  principal_id         = azurerm_user_assigned_identity.app.principal_id
}

resource "azurerm_cognitive_account" "openai" {
  name                  = "oai-${var.name}"
  location              = var.openai_location
  resource_group_name   = azurerm_resource_group.main.name
  kind                  = "OpenAI"
  sku_name              = "S0"
  custom_subdomain_name = "oai-${var.name}"
  local_auth_enabled    = true
  tags                  = local.tags
}

resource "azurerm_cognitive_deployment" "model" {
  for_each             = var.model_deployments
  name                 = each.key
  cognitive_account_id = azurerm_cognitive_account.openai.id
  model {
    format  = "OpenAI"
    name    = each.value.model
    version = each.value.version
  }
  sku {
    name     = "Standard"
    capacity = each.value.capacity
  }
}

resource "azurerm_key_vault_secret" "openai_key" {
  name         = "azure-openai-api-key"
  value        = azurerm_cognitive_account.openai.primary_access_key
  key_vault_id = azurerm_key_vault.main.id
}

resource "azurerm_search_service" "passages" {
  name                = "srch-${var.name}"
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  sku                 = "basic"
  replica_count       = 1
  partition_count     = 1
  tags                = local.tags
}

resource "azurerm_container_app_environment" "main" {
  name                       = "cae-${var.name}"
  location                   = azurerm_resource_group.main.location
  resource_group_name        = azurerm_resource_group.main.name
  log_analytics_workspace_id = azurerm_log_analytics_workspace.main.id
  tags                       = local.tags
}

resource "azurerm_container_app" "api" {
  name                         = var.name
  container_app_environment_id = azurerm_container_app_environment.main.id
  resource_group_name          = azurerm_resource_group.main.name
  revision_mode                = "Multiple"
  tags                         = local.tags

  identity {
    type         = "UserAssigned"
    identity_ids = [azurerm_user_assigned_identity.app.id]
  }

  secret {
    name                = "azure-openai-api-key"
    key_vault_secret_id = azurerm_key_vault_secret.openai_key.versionless_id
    identity            = azurerm_user_assigned_identity.app.id
  }

  ingress {
    external_enabled = true
    target_port      = 8080
    traffic_weight {
      latest_revision = true
      percentage      = 100
    }
  }

  template {
    min_replicas = 1
    max_replicas = 10

    http_scale_rule {
      name                = "http"
      concurrent_requests = "50"
    }

    container {
      name   = "api"
      image  = var.image
      cpu    = 0.5
      memory = "1Gi"

      env {
        name  = "AZURE_OPENAI_ENDPOINT"
        value = azurerm_cognitive_account.openai.endpoint
      }
      env {
        name        = "AZURE_OPENAI_API_KEY"
        secret_name = "azure-openai-api-key"
      }
      env {
        name  = "APPLICATIONINSIGHTS_CONNECTION_STRING"
        value = azurerm_application_insights.main.connection_string
      }

      liveness_probe {
        transport = "HTTP"
        port      = 8080
        path      = "/healthz"
      }
    }
  }

  depends_on = [azurerm_role_assignment.app_reads_secrets]
}

resource "azurerm_monitor_action_group" "oncall" {
  name                = "ag-${var.name}"
  resource_group_name = azurerm_resource_group.main.name
  short_name          = "agentops"
  email_receiver {
    name          = "oncall"
    email_address = var.alert_email
  }
  tags = local.tags
}

resource "azurerm_monitor_scheduled_query_rules_alert_v2" "handover_share" {
  name                 = "${var.name}-handed-to-people"
  resource_group_name  = azurerm_resource_group.main.name
  location             = azurerm_resource_group.main.location
  description          = "More conversations than usual go to a person: check the model deployment and confidence"
  severity             = 2
  scopes               = [azurerm_application_insights.main.id]
  evaluation_frequency = "PT15M"
  window_duration      = "PT1H"
  criteria {
    query                   = <<-KQL
      dependencies
      | where name == "conversation"
      | summarize handed = countif(tobool(customDimensions["agent.escalated"])), total = count()
      | extend share = todouble(handed) / todouble(total)
    KQL
    time_aggregation_method = "Maximum"
    metric_measure_column   = "share"
    operator                = "GreaterThan"
    threshold               = 0.25
  }
  action {
    action_groups = [azurerm_monitor_action_group.oncall.id]
  }
  tags = local.tags
}

resource "azurerm_monitor_scheduled_query_rules_alert_v2" "cost" {
  name                 = "${var.name}-cost-per-conversation"
  resource_group_name  = azurerm_resource_group.main.name
  location             = azurerm_resource_group.main.location
  description          = "Average model cost per conversation above the release budget"
  severity             = 3
  scopes               = [azurerm_application_insights.main.id]
  evaluation_frequency = "P1D"
  window_duration      = "P1D"
  criteria {
    query                   = <<-KQL
      dependencies
      | where name == "conversation"
      | summarize eur = avg(todouble(customDimensions["cost.eur"]))
    KQL
    time_aggregation_method = "Maximum"
    metric_measure_column   = "eur"
    operator                = "GreaterThan"
    threshold               = 0.006
  }
  action {
    action_groups = [azurerm_monitor_action_group.oncall.id]
  }
  tags = local.tags
}

output "api_url" {
  value = "https://${azurerm_container_app.api.ingress[0].fqdn}"
}

output "search_endpoint" {
  value = "https://${azurerm_search_service.passages.name}.search.windows.net"
}
