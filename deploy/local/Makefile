# Define variables for the cluster name and the path to your Kind configuration file
CLUSTER_NAME := my-cluster
KIND_CONFIG := ./kind.yaml
KUBECONFIG := $(HOME)/.kube/config-$(CLUSTER_NAME)

.PHONY: copy-env
copy-env:  ## Copy
	cp ../../.env .env

tilt-up:
	@KUBECONFIG=$(KUBECONFIG) tilt up

.PHONY: create-cluster
create-cluster:
	@kind create cluster --name $(CLUSTER_NAME) --config $(KIND_CONFIG) --kubeconfig $(KUBECONFIG)

.PHONY: delete-cluster
delete-cluster:
	@kind delete cluster --name $(CLUSTER_NAME)

.PHONY: restart
restart: delete-cluster create-cluster

# The default action when you just run `make`
default: restart

run-registry:
	docker run -d -p 5000:5000 --restart=always --name registry registry:2
