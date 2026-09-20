# COPR SCM builds: https://copr.fedorainfracloud.org/
# Create a project, method Git, this repo, make srpm via this file.
outdir ?= .

.PHONY: srpm
srpm:
	dnf -y install git-core rpm-build python3 python3-tomllib \
	  pyproject-rpm-macros 2>/dev/null || \
	  dnf -y install git-core rpm-build python3 pyproject-rpm-macros
	rm -rf /tmp/monitorcontrol-copr-source
	mkdir -p /tmp/monitorcontrol-copr-source
	./scripts/build-source-archive.sh /tmp/monitorcontrol-copr-source
	rpmbuild -bs \
	  --define "_sourcedir /tmp/monitorcontrol-copr-source" \
	  --define "_srcrpmdir $(outdir)" \
	  packaging/rpm/monitorcontrol.spec
