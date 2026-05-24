# Thesis Template

This is the template for Bachelor, Master, or other theses at the Chair of Machine Learning and Reasoning (Computer Science 6).

**README content:**

1. [Prerequisites](#prerequisites)
2. [Compiling](#compiling)
3. [Writing](#writing)

> Feel free to open a pull request if you think this template can be improved!

---

## Prerequisites

- [TeX Live](https://tug.org/texlive/)
- [Git LFS](https://git-lfs.com)

Of course, you need a TeX installation. While minimal distributions like BasicTeX seem tempting, installing the whole thing is strongly recommended, sparing you the headache of fighting against missing package errors. You can safely leave out GUI applications, though. On macOS, installing [mactex-no-gui](https://formulae.brew.sh/cask/mactex-no-gui) via [Homebrew](https://brew.sh) is a solid choice.

Additionally, if you use Git for version control, install Git LFS before you clone or push to this repository to handle large binary files gracefully.

## Compiling

This document needs to be compiled using LuaLaTeX. The output file is then written to `main.pdf`.
There are multiple options to do this, some of them are described below:

### Manually

In your command line, run the following:

```sh
lualatex main
biber main
lualatex main
lualatex main
```

### Make

Run `make`. This repository's [`makefile`](makefile) then runs the above automatically.  
You can remove auxiliary files with `make clean` or use `make pdf` to build and clean up in one command.

### Latexmk (recommended)

Run `latexmk main`.  
The [`.latexmkrc`](.latexmkrc) file ensures that LuaLaTeX is used. You can clean up with `latexmk -c -bibtex`.

### Visual Studio Code (recommended)

Install the [LaTeX Workshop](https://marketplace.visualstudio.com/items?itemName=James-Yu.latex-workshop) extension in VS Code and trigger `Build LaTeX project` with the recipe `latexmk` from the TeX-menu in your sidebar.  
Again, the [`.latexmkrc`](.latexmkrc) file ensures that LuaLaTeX is used. You can clean up by triggering `Clean up auxiliary files`.

Alternatively, set `"latex-workshop.latex.build.forceRecipeUsage": false` in your settings and build without a recipe to recognize the TeX magic commands at the beginning of `main.tex`.

### Overleaf

Unless you have Overleaf Pro, you won't be able to use [Overleaf](https://www.overleaf.com) with the template, as the compile time limit is too small. Instead we recommend using this ShareLaTeX installation provided to RWTH students: [RWTH/TU Darmstadt ShareLaTeX](https://sharelatex.tu-darmstadt.de). When using either, make sure to specify the following settings for the project to compile properly:

- Compiler: `LuaLaTeX`
- Main document: `main.tex`

## Writing

**Take a look at Chapter 0** (Template Instructions) in the [PDF](main.pdf) and the [source file](chapters/template-instructions.tex) to see what TeX commands to use for citations, cross-references, acronyms, figures, and more in this template. Some other tips follow here.

### Language

Decide whether you want to use American or British English. In the latter case, replace `american` in the `\usepackage{babel}` command in [resources/preamble.tex](resources/preamble.tex) with `british`.

Also decide on whether you want to include [Oxford commas](https://www.grammarly.com/blog/what-is-the-oxford-comma-and-why-do-people-care-so-much-about-it/). If not, remove the two corresponding settings at the end of [resources/preamble.tex](resources/preamble.tex).

### Title Page and Abstract

To populate the title page with your information, edit the commands at the top of [main.tex](main.tex). Try not to touch [resources/title-page.tex](resources/title-page.tex).

Insert your abstract into [chapters/abstract.tex](chapters/abstract.tex).

### Graphics and Other Resources

Put all your graphics or figures into the [graphics/](graphics/) directory. File paths in `\includegraphics` commands are relative to this directory. Use vector graphics instead of pixel images wherever possible.

Add all your references in biblatex format to [resources/references.bib](resources/references.bib). These will be sorted by author name, year, and title.

Define all your acronyms with the `\newacronym` command in [resources/acronyms.tex](resources/acronyms.tex). These will be printed alphabetically.

List all math symbols used with the `\glsxtrnewsymbol` command in [resources/symbols.tex](resources/symbols.tex). These will be listed in order of definition. To structure them into groups, use the `\newglsgroup` command and specify a group for each symbol.

You can define custom macros in [resources/macros.tex](resources/macros.tex). This can be useful for certain convoluted math expressions. Take a look at existing macros to find some that may be useful for you.

### Templates

The [templates/](templates/) directory contains a bunch of copy-and-paste snippets for adding figures and tables in various arrangements. Help yourself.

### Checklist

Here is an incomplete list of things to check and do once you think the thesis is more or less finished.

- [ ] Fix any remaining TeX errors and warnings (including overfull \hboxes).
- [ ] Update the contents of the `\glssetwidest` commands in [resources/preamble.tex](resources/preamble.tex) to your longest acronym and symbol (replace `RWTH` and `argmax ...`).
- [ ] Replace `\today` with `\formatdate{dd}{mm}{yyyy}` in [main.tex](main.tex) to fix the submission date.
- [ ] If your title spans over multiple lines, consider adding line breaks to balance line lengths (using `\\`).
- [ ] For printing, make sure you print on one side only. Alternatively, change the option `oneside` to `twoside` in the `\documentclass` command to get alternating (left/right) page numbers and margins.
- [ ] Add the option `final` to the `\documentclass` command.
- [ ] Double check if everything is included and laid out correctly in the PDF.
- [ ] For legal RWTH logo use on your thesis refer to [this page](https://www.rwth-aachen.de/cms/root/Studium/Im-Studium/Pruefungen-Abschlussarbeiten/~hjxv/Hinweise-zu-schriftlichen-Arbeiten/?lidx=1) with usage requirements.
