from .. import Partner
import sys 

if __name__ == '__main__':
    P = Partner.Partner(verbose = True, name = "school comp")
    P.set_partner(("10.50.3.181", 5000))
    if not P.connectPartner(): 
        print("connectPartner failed")
        sys.exit(0)
    P.send("hello from {}".format(P.name).encode())
    print(P.recv().decode())
    