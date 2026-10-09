terraform {
  backend "gcs" {
    bucket = "trainia-staging-tfstate"
    prefix = "terraform/state"
  }
}
