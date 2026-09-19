"""Content boundaries that must reject before database mutation."""
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))
import spire


class SpireValidationTests(unittest.TestCase):
    def column(self,name='chance',type='float',nullable=False,length=0):
        return dict(name=name,type=type,nullable=nullable,length=length)

    def test_integer_range_precision_and_flags(self):
        c=self.column('price','bigint unsigned')
        self.assertEqual(spire.validate('items',c,'18446744073709551615'),'18446744073709551615')
        for value in ('18446744073709551616','-1','1.5',True):
            with self.assertRaises(ValueError): spire.validate('items',c,value)
        with self.assertRaises(ValueError): spire.validate('aa_ability',self.column('enabled','tinyint'),'2')
        self.assertEqual(spire.validate('items',self.column('mana','int'),'-10'),'-10')

    def test_probability_and_nonfinite_numbers(self):
        for value in ('-0.01','100.01','NaN','Infinity','1e99'):
            with self.assertRaises(ValueError): spire.validate('lootdrop_entries',self.column(),value)
        self.assertEqual(spire.validate('lootdrop_entries',self.column(),'25.5'),'25.5')

    def test_decimal_storage_bounds(self):
        c=self.column('custom','decimal(6,2)')
        self.assertEqual(spire.validate('items',c,'9999.99'),'9999.99')
        for v in ('10000','0.001'):
            with self.assertRaises(ValueError): spire.validate('items',c,v)

    def test_export_strings_and_sql_literals(self):
        c=self.column('value','varchar(64)',True,64)
        for value in ('a^b','a\nb','a\rb','a\0b','x'*65):
            with self.assertRaises(ValueError): spire.validate('db_str',c,value)
        value="Zöe's \\ 100%_"
        self.assertEqual(spire.validate('db_str',c,value),value)
        self.assertNotIn(value,spire.literal(value));self.assertEqual(spire.validate('db_str',c,None),None)

    def test_high_spell_warning_and_item_reference(self):
        self.assertTrue(spire.warnings('spells_new',{'id':'45000'}))
        self.assertFalse(spire.warnings('spells_new',{'id':'44999'}))
        self.assertTrue(spire.warnings('aa_ranks',{'spell':'45000'}))
        self.assertFalse(spire.warnings('aa_ranks',{'spell':'65535'}))
        self.assertTrue(spire.warnings('items',{'clickeffect':'45000'}))
        self.assertTrue(any(x['table']=='spells_new' and x['filters']=={'id':'26'} for x in spire.links('items',{'id':'1','clickeffect':'26'})))

    def test_links_keep_composite_string_types_and_related_records(self):
        links=spire.links('db_str',{'id':'20','type':'4','value':'Description'})
        self.assertTrue(any(x['table']=='aa_ranks' and x['filters']=={'desc_sid':'20'} for x in links))
        self.assertFalse(any('title_sid' in x['filters'] for x in links))
        links=spire.links('aa_ranks',{'id':'1','desc_sid':'20','title_sid':'20'})
        self.assertTrue(any(x['filters']=={'id':'20','type':'4'} for x in links))
        self.assertTrue(any(x['filters']=={'id':'20','type':'1'} for x in links))
        links=spire.links('npc_types',{'id':'1','loottable_id':'10','merchant_id':'7'})
        self.assertTrue(any(x['table']=='merchantlist' and x['filters']=={'merchantid':'7'} for x in links))

    def test_android_deploys_both_new_modules(self):
        root=Path(__file__).resolve().parents[1]
        code=(root/'app/src/main/java/io/github/russianranger/trasc/RuntimeManager.java').read_text()
        for name in ('spire.py','spire_catalog.py'): self.assertIn('"'+name+'"',code)


if __name__=='__main__': unittest.main()
