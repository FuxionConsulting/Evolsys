# -*- coding: utf-8 -*-
from odoo.tests.common import TransactionCase
from odoo.exceptions import ValidationError

class TestPartnerRIF(TransactionCase):

    def setUp(self):
        super().setUp()
        self.Partner = self.env['res.partner']
        self.ve_country = self.env.ref('base.ve')

    def test_person_valid_rif(self):
        partner = self.Partner.create({
            'name': 'Persona Prueba',
            'company_type': 'person',
            'country_id': self.ve_country.id,
            'vat': 'v12345678',
        })
        self.assertEqual(partner.vat, 'V12345678')

    def test_person_invalid_rif_format(self):
        with self.assertRaises(ValidationError):
            self.Partner.create({
                'name': 'Persona Mala',
                'company_type': 'person',
                'country_id': self.ve_country.id,
                'vat': 'J12345678',
            })

    def test_company_valid_rif_juridica(self):
        partner = self.Partner.create({
            'name': 'Empresa Prueba',
            'company_type': 'company',
            'country_id': self.ve_country.id,
            'rif_type': 'J',
            'vat': 'j123456789',
        })
        self.assertEqual(partner.vat, 'J123456789')

    def test_company_invalid_rif_format(self):
        with self.assertRaises(ValidationError):
            self.Partner.create({
                'name': 'Empresa Mala',
                'company_type': 'company',
                'country_id': self.ve_country.id,
                'rif_type': 'J',
                'vat': 'J123',  # formato incorrecto
            })

    def test_company_inconsistent_rif_type(self):
        with self.assertRaises(ValidationError):
            self.Partner.create({
                'name': 'Empresa Inconsistente',
                'company_type': 'company',
                'country_id': self.ve_country.id,
                'rif_type': 'G',
                'vat': 'J123456789',  # empieza en J pero rif_type=G
            })
