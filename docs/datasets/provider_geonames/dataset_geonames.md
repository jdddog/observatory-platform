# GeoNames

"The GeoNames geographical database covers all countries.” It contains “over 25 million 
geographical names and consists of over 11 million unique features whereof 4.8 million 
populated places and 13 million alternate names. All features are categorized into one out of 
nine feature classes and further subcategorized into one out of 645 feature codes. 
GeoNames is integrating geographical data such as names of places in various languages, 
elevation, population and others from various sources.
 _- source: [GeoNames](https://www.geonames.org/about.html)_ 
and [data details](https://download.geonames.org/export/dump/readme.txt)

---

**Schema**

+ **geonameid** [*Integer*]
+ **name** [*String*]
+ **asciiname** [*String*]
+ **alternatenames** [*String*]
+ **latitude** [*Float*]
+ **longitude** [*Float*]
+ **featureclass** [*String*]
+ **featurecode** [*String*]
+ **countrycode** [*String*]
+ **cc2** [*String*]
+ **admin1code** [*String*]
+ **admin2code** [*String*]
+ **admin3code** [*String*]
+ **admin4code** [*String*]
+ **population** [*Integer*]
+ **elevation** [*String*]
+ **dem** [*Integer*]
+ **timezone** [*String*]
+ **modificationdate** [*Date*]

