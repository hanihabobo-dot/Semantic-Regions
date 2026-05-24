# root filename without .tex
file = main

.PHONY: main draft pdf clean

main:
	lualatex ${file}
	biber ${file}
	lualatex ${file}
	lualatex ${file}

draft:
	lualatex ${file}

pdf: main clean

clean:
	find . -type f -name "*.aux" -delete
	rm -f ${file}.auxlock ${file}.bbl ${file}.bcf ${file}.blg ${file}.fdb_latexmk ${file}.fls ${file}.loa ${file}.lof ${file}.log ${file}.lol ${file}.lot ${file}.tdo ${file}.toc ${file}.run.xml ${file}.synctex.gz *.synctex\(busy\) *.md5 indent.log *-SAVE-ERROR
