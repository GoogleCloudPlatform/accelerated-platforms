# GKE Base Platform

For additional information see the
[GKE Base Platform documentation](/docs/platforms/gke/base/README.md).

## Directory Structure

### **`_shared_config/`**

Contains the variables, `.tfvars` files, and other local configuration that can
be shared across Terraservices. These files enable efficient sharing of
configurations without relying on Terraform state files.

### **`core/`**

Provides the core Terraservices that form a flexible and scalable platform
foundation, built on industry best practices. The modular architecture allows
for easy integration of additional components and services, enabling the ability
to tailor a platform to specific needs and workloads.

### **`features/`**

A collection of additional Terraservices that can be incorporated to enhance the
platform's functionality.

### **`kubernetes/`**

Where the Kubernetes configuration and manifest files are generated for the
platform.

### **`modules/`**

A collection of opinionated Terraform modules to simplify operations that are
frequently performed on the platform.

### **`scripts/`**

A collection of reusable scripts for operations that are frequently performed on
the platform.

### **`use-cases/`**

Illustrative examples demonstrating how to utilize the platform as the
foundation.
