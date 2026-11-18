/MemTotal/ { memtotal=$2 }
/MemFree/ { memfree=$2 }
END { printf("%10.5f %10.5f\n", memtotal/10^9, memfree/10^9) }
