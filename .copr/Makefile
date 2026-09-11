# COPR SCM builds: https://copr.fedorainfracloud.org/
# Create a project, method Git, this repo, make srpm via this file.
outdir ?= .

.PHONY: srpm
srpm:
	dnf -y install git-core rpm-build python3 python3-tomllib 2>/dev/null || \
	  dnf -y install git-core rpm-build python3
	version=$$(python3 -c "import tomllib; print(tomllib.load(open('pyproject.toml','rb'))['project']['version'])")
	git archive --prefix=monitorcontrol-$${version}/ -o /tmp/monitorcontrol-$${version}.tar.gz HEAD
	rpmbuild -bs \
	  --define "_sourcedir /tmp" \
	  --define "_srcrpmdir $(outdir)" \
	  packaging/rpm/monitorcontrol.spec
