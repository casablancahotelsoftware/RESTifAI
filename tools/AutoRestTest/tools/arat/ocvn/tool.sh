#! /bin/bash
end=$((SECONDS+3600))

while [ $SECONDS -lt $end ]; do
    python ../../arat.py ../../../../specs/original/swagger/ocvn.yaml http://localhost:9004
done
