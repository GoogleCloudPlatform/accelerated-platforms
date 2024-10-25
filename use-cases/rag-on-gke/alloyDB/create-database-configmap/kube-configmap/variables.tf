
variable "name" {
  description = "The name of the module, to be append to each k8s resource name"
  type        = string
}
  
variable "configdata" {
  description = "The config data to be store in the configmap"
  type        = map(string)
}


variable "k8s_namespace" {
  description = "The k8s namespace to deploy resourcs to"
  type        = string
  default     = "default"
}
