terraform {
  backend "gcs" {
    bucket = "trainia-staging-tfstate"
    prefix = "envs/staging"
  }
}
