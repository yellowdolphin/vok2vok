# vok2vok
vok2vok is an open command-line xml-to-sqlite3 converter for vocabulary files intended to convert `vok2` files written by the 
[Teachmaster](https://www.teachmaster.de) vocabulary training software by Stefan Meyer.

## Usage
<pre><code>python vok2vok.py [-h] [--csv] [-f] [files ...]</pre></code>

As of now, it will convert the specified `.vok2` files into CSV files or `.vok5` files supported by Teachmaster 5 (version alpha 16). 
It will search for `.kk` files to preserve the box associated with each vocabulary item.
