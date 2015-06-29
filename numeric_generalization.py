#!/usr/bin/env python

from de_id_functions import *
import sys

# Working for year of birth and number of forum posts
def findBinEndpoints(qry, maxbinsize):
    """
   Given a max bin size, findBinEndpoints finds the appropriate endpoints
   that will create the smallest bins that have at least maxbinsize members.
   Note that this only works for integer bins.
   Note that if bins, for example, should be [1893-1917, 1918-1928, 1929-1931, etc.]
   then the endpoints will be: [1892,1917,1928,1931] : in other words, the endpoints of each interval.
    """
    i=0
    runningtotal = 0
    binbreaks = [int(qry[0][0])-1]
    binmeans = []
    # Keep track of how many of each value there are in order to help calculate the mean at the end
    valuedict = {}
    while i < len(qry)-1:
        runningtotal += qry[i][1]
        valuedict[qry[i][0]] = qry[i][1]
        # if running total of bins exceeds bin size, add as endpoint and start again
        # only if the remaining buckets have enough to also create a bin
        if runningtotal >= maxbinsize and sum([x[1] for x in qry[i+1:]]) >= maxbinsize:
            try: toappend = int(qry[i][0])
            except: toappend = qry[i][0]
            binbreaks.append(toappend)
            # Don't count the average of "NA" values (which were mapped to 9999)
            if 9999 in valuedict.keys():
                binmeans.append('NA')
            else:
                binmeans.append(float(sum(k*v for k,v in valuedict.items()))/sum(valuedict.values()))
            runningtotal = 0
            valuedict = {}
        # If remaining do not have enough to make a bin, then don't add this
        # as an endpoint and just finish up by adding the last endpoint.
        elif runningtotal >= maxbinsize and sum([x[1] for x in qry[i+1:]]) < maxbinsize:
            try: toappend = int(qry[len(qry)-1][0])
            except: toappend = qry[len(qry)-1][0]
            if qry[len(qry)-1][0] == '9999':
                binbreaks.append('NA')
            else:
                binbreaks.append(toappend)
            runningtotal = 0
            return binbreaks
        i = i+1
    try: toappend = int(qry[len(qry)-1][0])
    except: toappend = qry[len(qry)-1][0]
    # append max value as the last endpoint
    if qry[len(qry)-1][0] == 9999:
        binbreaks.append(9999)
        binmeans.append('NA')
    else:
        binbreaks.append(toappend)
    return binbreaks,binmeans


# Creates a dictionary that maps each unique value onto a corresponding
# range that takes endpoints
def createConversionDict(cursor, tableName, varName, endpoints, means):
    """
    This takes in a list of endpoints as generated by findBinEndpoints and then
    creates a dictionary whose keys take on the value of all unique values
    of a given column, and whose corresponding values are the bin that each
    of the unique values in the dataset should be mapped onto.
    """
    print "lalalala", len(endpoints),len(means)
    cursor.execute("SELECT " + varName + ", COUNT(*) as \'num\' FROM " + tableName + " GROUP BY " + varName)
    qry = cursor.fetchall()
    try: qry = [(int(float(z[0])),z[1]) for z in qry] # convert string floats to ints in qry count
    except: pass
    numDict = {}  # dictionary of unique values of value and how many times each occurs
    for item in qry:
        try:
            numDict[int(item[0])] = item[1]
        except:
            numDict[item[0]] = item[1]
    keys_sorted = sorted(numDict)
    keys_num = keys_sorted[:]
    for j in keys_num:
        if type(j) != int:
            keys_sorted.pop(keys_sorted.index(j))
    minBin = min(keys_sorted)
    maxBin = max(keys_sorted)
    binMap = {}
    for i in range(1, len(endpoints)):
        # if bin of length 1
        if endpoints[i] == endpoints[i - 1] + 1:
            binMap[endpoints[i]] = [str(endpoints[i]),means[i-1]]
        else:
            for num in range(endpoints[i - 1], endpoints[i] + 1):
                if num == endpoints[i - 1]:
                    continue
                binMap[num] = [str(endpoints[i - 1] + 1) + "-" + str(endpoints[i]),means[i-1]]
    newNumDict = {}
    for item in numDict:
        if item in binMap.keys():
            newNumDict[unicode(item)] = binMap[item]
        else:
            newNumDict[unicode(item)] = str(item)
    return newNumDict


# Creates a SQL table with mappings from unique values to binned values and means of those bins
def dictToTable(c, bin_dict, origVarName):
    """
    This takes in the dictionary as outputted by createConversionDict and
    then creates a table with original values, binned values, and mean binned values.
    """
    # Convert dictionary into a list of lists, each representing a row
    dict_list = []
    for k, v in bin_dict.iteritems():
        dict_list.append([k, v[0],v[1]])
    # Build conversion table for year of birth
    # Create table that contains conversion from original YoB values to their binned values
    # (if it doesn't already exist)
    try:
        c.execute("DROP TABLE " + origVarName + "_bins")
    except:
        pass
    c.execute("CREATE TABLE " + origVarName + "_bins (orig_" + origVarName + " text, binned_" + origVarName + " text, mean_" + origVarName + " text)")

    # Insert each item of the dictionary
    for item in dict_list:
        c.execute("INSERT INTO " + origVarName + "_bins VALUES (?,?,?)",item)

def main(dbname):
    c = dbOpen(dbname)
    table = 'source'
    global qry, endpts, year_conversion, nforumposts_conversion
    ########################################################
    # Bin years of birth
    # Replace all values of YoB that are blank with a temporary 9999
    c.execute("UPDATE " + table + " SET YoB = \'9999.0\' WHERE YoB = ''")
    c.execute("SELECT YoB, COUNT(*) as \'num\' FROM " + table + " GROUP BY YoB")
    qry = c.fetchall()
    try: qry = [(int(float(z[0])),z[1]) for z in qry] # convert string floats to ints in qry count
    except: pass
    print qry
    # Bin year of birth
    endpts,means = findBinEndpoints(qry, YoB_binsize)
    print endpts,means
    print len(endpts),len(means)
    # Create dictionary that maps every unique value to a corresponding bin
    year_conversion = createConversionDict(c, table, "YoB", endpts,means)
    # Delete the 9999 key, which corresponds to a NA value
    del year_conversion['9999']
    # Map an NA value back to NA
    year_conversion['NA'] = 'NA'
    print "conversion dict," , year_conversion
    # Convert dictionary to table named YoB_bins
    dictToTable(c, year_conversion, "YoB")
    # Check that the table values are correct
    c.execute("SELECT * FROM YoB_bins")
    c.fetchall()
    ########################################################
    # Bin number of forum posts
    # Replace all values of nforum_posts that are blank with a temporary 9999
    c.execute("UPDATE " + table + " SET nforum_posts = \'9999.0\' WHERE nforum_posts = ''")
    c.execute("SELECT nforum_posts, COUNT(*) as \'num\' FROM " + table + " GROUP BY nforum_posts ORDER BY nforum_posts")
    qry = c.fetchall()
    try: qry = [(int(float(z[0])),z[1]) for z in qry] # convert string floats to ints in qry count
    except: pass
    qry = sorted(qry, key=lambda x: int(x[0]))
    endpts,means = findBinEndpoints(qry, nforum_post_binsize)
    # Create dictionary that maps every unique value to a corresponding bin
    nforumposts_conversion = createConversionDict(c, table, "nforum_posts", endpts,means)
    # Convert dictionary to table named YoB_bins
    dictToTable(c, nforumposts_conversion, "nforum_posts")
    # Check that the table values are correct
    c.execute("SELECT * FROM nforum_posts_bins")
    c.fetchall()
    #c.execute('Pragma table_info(source)')
    #print c.fetchall()


if __name__ == '__main__':
    dbname = sys.argv[1]
    main(dbname)