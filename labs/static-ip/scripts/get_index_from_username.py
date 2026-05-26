#!/usr/bin/env python3
import sys
import hashlib

def main():
    if len(sys.argv) < 3:
        print("0")
        return
    
    username = sys.argv[1]
    nb_variantes = int(sys.argv[2])
    
    # Utiliser hashlib pour un hash déterministe
    hash_object = hashlib.md5(username.encode('utf-8'))
    hash_int = int(hash_object.hexdigest(), 16)
    
    # Index basé sur le hash
    index = hash_int % nb_variantes
    
    print(index)

if __name__ == "__main__":
    main()