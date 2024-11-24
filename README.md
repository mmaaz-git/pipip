# pipip

Solving Boolean satisfiability problems and integer programming with Python packaging.

## Background

Because Python package dependency resolution is NP-complete, any Boolean satisfiability (SAT) or (0/1 linear) integer programming (IP) problem can be encoded as a package dependency resolution problem, and then solve them with `pip` or `uv`. And since any NP-complete problem can be transformed into any other NP-complete problem, and often easily into SAT or IP, this gives a way to solve any NP-complete problem using Python packaging.

This code is called `pipip`: "pip" + "ip" for integer programming, and I just thought it sounded funny.

For how it works, see my [blog post](https://www.mmaaz.ca/writings/pipip.html).

Essentially, `satsolver.py` takes a SAT instance, encodes it as a package dependency resolution problem, then attempts to resolve it. `ipsolver.py` takes an IP instance, encodes it into a SAT instance, then uses `satsolver.py` to solve it.

## Usage

There are two files, `satsolver.py` and `ipsolver.py`, which solves SAT and IP problems respectively. You can either import their functions into your project, or run them as scripts.

`satsolver.py` takes a file with a DIMACS-CNF encoding of a SAT problem, and outputs a satisfying assignment if one exists. Lines beginning with `c` are ignored. There are examples in the `examples/sat` directory.

```
python satsolver.py examples/sat/001.cnf
```

`ipsolver.py` takes a plain-text file containing the IP instance in the form $Ax \leq b$, where the file contains one row per constraint, and the numbers are space-separated, and the final number is the right-hand side of the constraint. Lines beginning with `c` are ignored. There are examples in the `examples/ip` directory.

```
python ipsolver.py examples/ip/001.txt
```

While attempting to solve even small SAT or IP instances, I ran into issues with `pip-compile` due to its computational limits. To get around this, you can add the `--uv` flag to use `uv` instead, which is much faster.

```
python ipsolver.py examples/ip/005.txt --uv
```

There are examples of small SAT instances, larger ones from the SATLIB benchmark, simple IP instances, as well as some classic combinatorial problems, namely subset sum and set covering.

See my [blog post](https://www.mmaaz.ca/writings/pipip.html) for more details on the problems and the runtimes.
